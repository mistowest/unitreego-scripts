import sys
from unitree_webrtc_connect import SPORT_CMD, SPORT_CMD_MCF

print("Python:", sys.executable)
print("unitree_webrtc_connect: OK")
print("SPORT_CMD:", len(SPORT_CMD), "comandos")
print("SPORT_CMD_MCF:", len(SPORT_CMD_MCF), "comandos")
print("Hello:", SPORT_CMD.get("Hello"))
print("BackFlip MCF:", SPORT_CMD_MCF.get("BackFlip"))
