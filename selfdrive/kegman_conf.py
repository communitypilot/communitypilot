import json
import copy
import os
import threading
import time
from selfdrive.swaglog import cloudlog
from common.basedir import BASEDIR

def read_config():
  default_config = {"cameraOffset": 0.06, "lastTrMode": 1, "battChargeMin": 90, "battChargeMax": 95,
                    "wheelTouchSeconds": 1800, "battPercOff": 25, "carVoltageMinEonShutdown": 11200,
                    "brakeStoppingTarget": 0.25, "angle_steers_offset": 0, "brake_distance_extra": 1,
                    "lastALCAMode": 1, "brakefactor": 1.2, "lastGasMode": 0, "lastSloMode": 1,
                    "leadDistance": 5, "useCarCaching": True, "autoUpdate": True, "SpeedLimitOffset": 0, "LimitSetSpeed": True}

  if os.path.isfile(kegman_file):
    try:
      with open(kegman_file, "r") as f:
        config = json.load(f)
    except:
      cloudlog.exception("reading kegman.json error")
      config = default_config
    for i in default_config:
      if i not in config:
        variables_written.append(i)
        config.update({i: default_config[i]})

    # force update
    if config["carVoltageMinEonShutdown"] == "11800":
      config.update({"carVoltageMinEonShutdown": 11200})
    if int(config["wheelTouchSeconds"]) < 200:
      config.update({"wheelTouchSeconds": 1800})
    if int(config["battChargeMin"]) == 85:
      config.update({"battChargeMin": 90})
    if int(config["battChargeMax"]) == 90:
      config.update({"battChargeMax": 95})
  else:
    write_config(default_config)
    config = default_config
  return config

def kegman_thread():  # read and write thread; now merges changes from file and variable
  global conf
  global thread_counter
  global variables_written
  global thread_started
  global last_conf
  try:
    while True:
      thread_counter += 1
      time.sleep(thread_interval)  # every n seconds check for conf change
      with open(kegman_file, "r") as f:
        conf_tmp = json.load(f)
      if conf != last_conf or conf != conf_tmp:  # if either variable or file has changed
        thread_counter = 0
        if conf_tmp != conf:  # if change in file
          changed_keys = []
          for i in conf_tmp:
            try:
              if conf_tmp[i] != conf[i]:
                changed_keys.append(i)
            except:  # if new param from file not existing in variable
              changed_keys.append(i)
          for i in changed_keys:
            if i not in variables_written:
              conf.update({i: conf_tmp[i]})
        if conf != conf_tmp:
          write_config(conf)
        last_conf = copy.deepcopy(conf)
      variables_written = []
      if thread_counter > ((thread_timeout * 60.0) / thread_interval):  # if no activity in 15 minutes
        print("Thread timed out!")
        thread_started = False
        return
  except:
    print("Error in kegman thread!")
    cloudlog.warning("error in kegman thread")
    thread_started = False

def write_config(conf):  # never to be called outside kegman_conf
  if BASEDIR == "/data/openpilot" or BASEDIR == "/data/openpilot.arne182":
    with open(kegman_file, "w") as f:
      json.dump(conf, f, indent=2, sort_keys=True)
      os.chmod(kegman_file, 0o764)

def save(data):  # allows for writing multiple key/value pairs
  global conf
  global thread_counter
  global thread_started
  global variables_written
  thread_counter = 0
  if not thread_started and (BASEDIR == "/data/openpilot" or BASEDIR == "/data/openpilot.arne182"):
    threading.Thread(target=kegman_thread).start()  # automatically start write thread if file needs it
    thread_started = True
    print("Starting thread!")
  for key in data:
    variables_written.append(key)
  conf.update(data)

def get(key=None, default=None):  # can specify a default value if key doesn't exist
  global thread_counter
  if key is None:  # get all
    return conf
  else:
    thread_counter = 0
    return conf[key] if key in conf else default

thread_counter = 0  # don't change
thread_timeout = 5.0  # minutes to wait before stopping thread. reading or writing will reset the counter
thread_interval = 30.0  # seconds to sleep between checks
thread_started = False
kegman_file = "/data/kegman.json"
variables_written = []
conf = read_config()
last_conf = copy.deepcopy(conf)
