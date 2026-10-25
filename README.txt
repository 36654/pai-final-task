pai_tools — Physical AI 最終課題のツール(2026-10-25 版)

置き場所: Google Drive の「PAI2026 Workspace」の中に pai_tools フォルダごと置く。
データ(lerobot_dataset、checkpoints、lerobot_src)も同じ PAI2026 Workspace 直下。

【毎回の流れ】
  新しい端末・コンテナを作り直したとき: setup_machine.bat(何度実行しても安全)。評価とデモ生成は、開始時に環境を自動で確認・修正する(setup_machine の実行有無を覚えておく必要はない。Gazebo とロボットの再起動だけは人が行う)
  Gazeboとロボットを「いつもの方法」(ブラウザのデスクトップ内)で起動してから、Gazebo要のものを実行する。
  データの受け渡し: xfer_WRITE.bat(下の【データの受け渡し】)。上書きも削除もしない。
  結果の保存: save_outbox.bat 名前(評価のあと、動画などを Drive の results へ移す)

【規約(Fool Proof / Fail Safe)】
  ・台帳: tools\MANIFEST.txt が、全ファイルの基準(ハッシュと役割)。ツールを変えたら tools_audit.bat で、台帳との差・未登録・埋め込み・重複を確認する。
  ・名前の末尾が _WRITE の bat は、状態を変える。それ以外は読み取り専用(Gazebo内の評価を含む)。
  ・既存のデータ・チェックポイントを、上書きも削除もしない。名前が衝突したら別名(__from_drive_日時 / __from_pc_日時)で追加する。
  ・チェックポイントの名前は「種類_ステップ数_日付」(例 s1_region_act30k_1021)。現行の名前は tools\names.conf に書く。
  ・道具(.py / .sh)の正本は tools フォルダだけ。bat の中に道具を埋め込まない(古い版が戻る事故を防ぐ)。
  ・使い捨てのツールは pai_tools\_once\ へ移す(削除しない)。置き換えた古い版は _once\_bak_日時\ に残る。
  ・eval_act は、開始前に腕の追従を確認する。追従しなければ待ち、待っても追従しなければ評価を始めずに止まる。

【基盤】
  setup_machine.bat    新しい端末の初期化(コンテナ起動、ツール配置、カメラ追加、指の摩擦1.5)。何度実行しても安全
  xfer_WRITE.bat       Drive とコンテナの間でデータを移す(追加のみ)。xfer_WRITE.bat in|out ckpt|data|lay 名前
                         in = Drive→コンテナ、out = コンテナ→Drive。ckpt = checkpoints\train\名前、data = lerobot_dataset\名前、lay = 学習配置の json
                         例: xfer_WRITE.bat in ckpt s1_region_act30k_1021
                         同名があり内容が同じなら何もしない。違えば別名で追加する。最後に RESULT=OK を確認する
  drive_dir.bat        Drive の同期フォルダを自動検出して drive_path.txt に保存。検出し直し: drive_dir.bat reset
  save_outbox.bat 名前  Desktop\outbox の中身を Drive の results\日付_名前 へ移す
  cexec.bat            内部用。tools内のシェルをコンテナで実行し、outbox をデスクトップにコピー
  set_camera.bat       俯瞰カメラと動画用の正面カメラをワールドに追加(setup_machine が呼ぶ。反映にはGazeboの再起動が必要)
  finger_friction.bat  指の摩擦係数を書き換える(setup_machine が呼ぶ。反映にはGazeboとロボットの再起動が必要)
  grab_camera.bat      カメラ画像を保存(cam.png、cam_side.png)。画角の確認用。Gazebo要
  stop_grid.bat        実行中のまとめ測定(seen_all / smolvla_all / eval_smolvla など)を止める。Gazeboは止めない

【デモ生成】
  expert_episode.bat   専門家のデモ生成+動画+プレビュー(Gazebo要)。例: expert_episode.bat 20 --name fin --keep-failures --probe
  expert_video.bat     保存済みのnpzから動画(mp4)を作り直す
  pick_region.bat      既存のデモから、角度が範囲内の成功件だけを新しい名前にコピー(元は変えない)
  make_dataset.bat     npz → LeRobot v2.1(成功したデモだけ)

【学習】
  tools\colab\act_train.ipynb  Colab(GPU)でACTを学習。保存名 RUN は日付入りで、既にあれば止まる。学習後に train_args.json と照合する。「ランタイム → すべてのセルを実行」で最後まで進む

【ステージ2: 積み木2個・言語指示で対象を選ぶ】(10/24)
  目的: 同じ画面(赤と青)で、指示「put the red block in the box」「…blue…」により取る積み木が変わるか(SmolVLA)。ACT は言語を受け取れない。学習していない色(黄色)を指示で選べるかも測る。
  video_WRITE.bat      提出用の動画を作る。video_plan.txt(台本: 場面・システム構成図・クリップ・字幕・倍速。倍速は動画内か概要欄に明記する。講座の文書は2倍速まで、運営の回答は8倍速でも可(10/25))に従い、Drive の results のクリップを左(正面)右(天井・180°回転)に並べて MP4 にする。Desktop\outbox\PAI_movie_日時.mp4 を新規に作る(上書きしない)。Gazebo不要、約1〜3分。講座のオープニング/エンディング(*OP.mp4 / *ED.mp4)は pai_tools\assets に、スライド画像(s1〜s8: 課題・構成・手法・2方策・配置の考え方・成功の基準・段階2・結果)は pai_tools\assets\slides に置く(台本の jingle 行、image 行)
  stage2_gen_WRITE.bat [convert|pair|pairconvert|mix|mixconvert]   デモ生成(約2.6時間)+LeRobot変換+Driveへの移送。色は赤・青・緑から毎回2色。データ名は tools\names.conf の S2DATA(日付入り。既にあれば止まる)。最初の10件の成功率が70%未満なら自動停止。convert=生成済みで変換と移送だけやり直す。mix=S2PAIR とステージ1の単一ブロックのデモ(DATA)を合わせた S2MIX を作る(Gazebo不要、約10分。2回目の評価で条件Cが3/10だったため)
                         pair=S2DATA と同じ画面(同じ位置・同じ色)で対象だけ入れ替えたデモ(約2.4時間)を作り、S2DATA と合わせて S2PAIR にして変換・移送する(元のデータは変更しない)。pairconvert=その変換と移送のやり直し
  経緯(10/24): S2DATA のモデルは、学習した配置は再現したが、対象を入れ替えた指示は 0/6(画面を覚えるだけで指示を使っていなかった。各画面の対象が1通りだったため)。そこで pair で、同じ画面に対象2通りのデモを揃えた
  vla_diag.bat URL TOKEN   SmolVLAの診断(Gazebo不要・約5分・何も変更しない)。学習デモの画面での出力と専門家の差/指示を替えたときの旋回の向き/評価中の腕の動き(閉じた位置)。結果 Desktop\outbox\vla_diag.txt
  次に Colab で tools\colab\smolvla_train.ipynb を実行(S2PAIR。30,000ステップ、約115分。保存先は <データ名>_smolvla。既にあれば止まる)
  stage2_eval.bat act    現行のACT(names.conf の ACT30K)で条件 C → A → B を測る(30回、約40分)
  stage2_eval.bat seen URL TOKEN   条件S(SmolVLA。学習に使った配置の再現を、学習と同じ指示と、対象を入れ替えた指示で。12回、約40分)。画面を覚えているだけか、指示を使っているかを分ける
  stage2_eval.bat vla URL TOKEN   ステージ2のSmolVLA(names.conf の S2_SMOLVLA)で条件 C → A → B を測る(40回)。URL/TOKEN は smolvla_infer.ipynb のセル5の出力(モデル名はセル1の NAME 1か所だけ書き換える。セル6はトンネルの疎通を1分ごとに確認する)
  (評価とデモ生成は、開始時に tools/env_gate.py が環境を確認する: 指の摩擦 mu1 が 6 か所とも 1.5、Gazebo の起動が xacro の更新より新しい。摩擦が違えば finger_friction.sh で自動的に書き換える。満たさなければ測定せず終了コード3で止まる。確認した値は結果ファイルの先頭に残る。--skip-env-gate で省けるが、省いた結果は環境未確認と明記する)
  条件 A=赤+青(SmolVLAは指示を替えて2回。ACTは配置ごと1回で両方の対象として採点) B=黄色(未学習)が対象・赤が妨害物 C=青1個。配置は10個、ACT と SmolVLA で同じ(seed 2000)。成功=指示した積み木だけが箱に入った
  結果は Wilson 区間つきの [要約] と、失敗の内訳(ok / wrong=別の積み木 / both / none)。各回の動画は Desktop\outbox。終わったら save_outbox.bat 名前 で Drive へ

【評価】(Gazebo要)
  eval_act.bat         学習済みACTを、毎回ちがう配置でN回走らせて成功率を測る。例: eval_act.bat s1_region_act30k_1021 --n 20 --te
                         開始前に腕の追従を確認する。ホームに戻った時点で打ち切って判定。--te で時間方向のアンサンブル(結果ファイル名に _te)
  seen_all.bat         学習に使った最初の10配置の再現(seen)を、ACT 30k・80k(と、URL TOKEN があれば SmolVLA)で測る。名前は tools\names.conf
  smolvla_all.bat      SmolVLA を、ACTと同じ20配置・格子15配置で測り、専門家と並べる(URL TOKEN が必要)
  eval_smolvla.bat     SmolVLA を N 回走らせて成功率を測る
  infer_act.bat        学習済みACTでロボットを動かす(Gazebo起動後)
  trace_stats.bat      eval_act が記録した指令・関節角を、専門家のデモと比べる(Gazebo不要)
  smolvla_env.bat      SmolVLA用の別の仮想環境の作成と動作確認

【診断・確認】(何も変更しない)
  env_check.bat        環境の確認だけ(何も変更しない): 指の摩擦、Gazebo の起動順、チェックポイントのハッシュ。評価・デモ生成の開始時の自動確認(tools/env_gate.py)と同じ
  policy_offline.bat   Gazebo なしで、学習デモの画像を方策に入れ、指令を専門家と比べる(約3分)
  traj_dump.bat        直近の評価の指令と関節角の時系列を出す
  drive_usage.bat      Drive のどのフォルダが容量を使っているかを大きい順に出す
  tools_audit.bat      pai_tools の全ファイルを点検する(台帳との差、未登録、bat への道具の埋め込み、重複、eval_act.py が新しい版か)。結果は Desktop\outbox_ckpt\tools_audit.txt

【更新】
  update_tools_WRITE.bat  ツール群を更新する(計画を見せて YES を入力。置き換えた古い版は _once\_bak_日時\ に残る)。台帳(MANIFEST.txt)もこれで更新する

【削除済み・退避済み】
  削除(10/17): cleanup_tools、migrate_to_drive、release_sweep、grip_geom
  _once へ退避(10/22): act_sweep、eval_slow、diag_all、grid_all(古い eval_act.py を埋め込んでいた)、sync_in / sync_out / sync_act / sync_smolvla(同名を上書き・削除する。xfer_WRITE に置き換え)、train_act(ローカル学習。保存名の取り違えの原因になった)、tidy_outbox、その日限りの取り込み・確認・パッチ用 bat
  10/22(2回目): tools にあった、退避した bat の道具(act_sweep.sh、diag_all.sh、grid_all.sh、preflight.sh、ckpt_check.sh、ckpt_hash.ps1、ckpt_img_check.py)、バックアップ(eval_act.py.bak_*)、重複(act_train_20261021.ipynb、tools\fetch_eval_src.bat)を _once\tools へ退避
  10/24: tools にあった M1(お辞儀デモ)用の eval_img.sh、pai_img\\eval_img.py、train_img.sh(どこからも呼ばれていなかった)を _once\\tools へ退避
  起動後の最初の1件でアームが追従しないことがある。Gazeboを再起動すると直る(10/24)
  10/24: xfer_WRITE.bat ほか4つのbatの日本語を英数字に直した(日本語の行があると、この環境で「age: is not recognized」と出て途中で終わることがあった)
