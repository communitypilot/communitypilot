import zmq
import selfdrive.messaging as messaging
from selfdrive.services import service_list
import selfdrive.kegman_conf as kegman
import subprocess
from common.basedir import BASEDIR

class Phantom():
  def __init__(self, timeout=False, do_sshd_mod=False):
    context = zmq.Context()
    self.phantom_Data_sock = messaging.sub_sock(context, service_list['phantomData'].port, conflate=True)
    self.data = {"status": False, "speed": 0.0}
    self.last_receive_counter = 0
    self.last_phantom_data = {"status": False, "speed": 0.0}
    self.timeout = timeout
    self.to_disable = True
    if (BASEDIR == "/data/openpilot") and (not kegman.get("UseDNS") or kegman.get("UseDNS") is None) and do_sshd_mod:  # ensure we only run once
      self.mod_sshd_config()

  def update(self, rate=40.43):  # in the future, pass in the current rate of long_mpc to accurate calculate disconnect time
    phantomData = messaging.recv_one_or_none(self.phantom_Data_sock)
    if phantomData is not None:
      self.data = {"status": phantomData.phantomData.status, "speed": phantomData.phantomData.speed, "angle": phantomData.phantomData.angle, "time": phantomData.phantomData.time}
      self.last_phantom_data = dict(self.data)
      self.last_receive_counter = 0
      self.to_disable = not self.data["status"]
    else:
      if self.to_disable:  # if last message is status: False, disable phantom mode, also disable by default
        self.data = {"status": False, "speed": 0.0}
      elif self.last_receive_counter > int(rate * 1.0) and self.timeout:  # lost connection, don't disable. keep phantom on but set speed to 0
        self.data = {"status": True, "speed": 0.0, "angle": 0.0, "time": 0.0}
      else:  # if waiting between messages from app, message becomes none, this uses the data from last message
        self.data = dict(self.last_phantom_data)
      self.last_receive_counter = min(self.last_receive_counter + 1, 900)  # don't infinitely increment

  def mod_sshd_config(self):  # this disables dns lookup when connecting to EON to speed up commands from phantom app, reboot required
    sshd_config_file = "/system/comma/usr/etc/ssh/sshd_config"
    try:
      result = subprocess.check_call(["mount", "-o", "remount,rw", "/system"])  # mount /system as rw so we can modify sshd_config file
    except:
      result = 1
    if result == 0:
      with open(sshd_config_file, "r") as f:
        sshd_config = f.read()
      if "UseDNS no" not in sshd_config:
        if sshd_config[-1:]!="\n":
          use_dns = "\nUseDNS no\n"
        else:
          use_dns = "UseDNS no\n"
        with open(sshd_config_file, "w") as f:
          f.write(sshd_config + use_dns)
        kegman.save({"UseDNS": True})
      else:
        kegman.save({"UseDNS": True})
      try:
        subprocess.call(["mount", "-o", "remount,ro", "/system"])  # remount system as read only
      except:
        pass
    else:
      kegman.save({"UseDNS": False})
