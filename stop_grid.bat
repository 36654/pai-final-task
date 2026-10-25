@echo off
chcp 65001 >nul
rem grid_all / smolvla_all などの測定をコンテナの中で止める。コンテナ自体と Gazebo は止めない。
rem 先に、段階を順に進める親のスクリプトを止めてから、評価本体を止める(逆だと次の段階が始まってしまう)
docker exec pai_ros2 bash -c "pkill -f '[s]molvla_all.sh'; pkill -f '[g]rid_all.sh'; pkill -f '[d]iag_all.sh'; pkill -f '[e]val_smolvla.sh'; sleep 1; pkill -f '[e]xpert_episode.py'; pkill -f '[e]val_act.py'; pkill -f '[s]molvla_server.py'; pkill -f '[p]arameter_bridge'; sleep 1; echo --- 残っている測定の処理 ---; pgrep -af 'grid_all|diag_all|expert_episode|eval_act|smolvla_server|smolvla_all' || echo なし"
echo.
echo 止めました。このあとコンソールの窓は閉じてかまいません。
pause
