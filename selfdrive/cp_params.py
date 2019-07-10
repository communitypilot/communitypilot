import json
import copy
import os
import threading
import time
from selfdrive.swaglog import cloudlog
from common.basedir import BASEDIR

'''
  -- cp_params syntax --
  to import: import selfdrive.cp_params as cp_params
  
  to save a parameter to file: cp_params.save({'_AWARENESS_TIME': 300})
  
  to save multiple parameters to file: cp_params.save({'angle_steers_offset': 1.2, 'other_key': True})
  
  to retrieve a parameter: cp_params.get("userID")
  note, if the key does not exist, by default None will be returned
  
  if you would like to specify a custom default value to be returned if the key does not exist, you can run:
  cp_params.get("TR", 1.8)
  
  to get all parameters:
  cp_params.get()
'''

params = {}
def read_params():
  global params
  default_params = {"CAMERA_OFFSET": 0.06}

  if os.path.isfile(params_file):
    try:
      with open(params_file, "r") as f:
        params = json.load(f)
    except:
      cloudlog.exception("reading cp_params.json error")
      params = default_params
    for i in default_params:
      if i not in params:
        params.update({i: default_params[i]})
  else:
    write_params(default_params)
    params = default_params

def cp_params_thread():  # read and write thread; now merges changes from file and variable
  global params
  global thread_counter
  global variables_written
  global thread_started
  global last_params
  try:
    while True:
      thread_counter += 1
      time.sleep(thread_interval)  # every n seconds check for params change
      with open(params_file, "r") as f:
        para_tmp = json.load(f)
      if params != last_params or params != para_tmp:  # if either variable or file has changed
        thread_counter = 0
        if para_tmp != params:  # if change in file
          changed_keys = []
          for i in para_tmp:
            try:
              if para_tmp[i] != params[i]:
                changed_keys.append(i)
            except:  # if new param from file not existing in variable
              changed_keys.append(i)
          for i in changed_keys:
            if i not in variables_written:
              params.update({i: para_tmp[i]})
        if params != para_tmp:
          write_params(params)
        last_params = copy.deepcopy(params)
      variables_written = []
      if thread_counter > ((thread_timeout * 60.0) / thread_interval):  # if no activity in 5 minutes
        print("Thread timed out!")
        thread_started = False
        return
  except:
    print("Error in cp_params thread!")
    cloudlog.warning("error in cp_params thread")
    thread_started = False

def write_params(para):  # never to be called outside cp_params
  if BASEDIR == "/data/openpilot":
    with open(params_file, "w") as f:
      json.dump(para, f, indent=2, sort_keys=True)
      os.chmod(params_file, 0o764)

def save(data):  # allows for writing multiple key/value pairs
  global params
  global thread_counter
  global thread_started
  global variables_written
  thread_counter = 0
  if not thread_started and (BASEDIR == "/data/openpilot"):
    threading.Thread(target=cp_params_thread).start()  # automatically start write thread if file needs it
    thread_started = True
    print("Starting thread!")
  for key in data:
    variables_written.append(key)
  params.update(data)

def get(key=None, default=None):  # can specify a default value if key doesn't exist
  global thread_counter
  if key is None:  # get all
    return params
  else:
    thread_counter = 0
    return params[key] if key in params else default

thread_counter = 0  # don't change
thread_timeout = 5.0  # minutes to wait before stopping thread. reading or writing will reset the counter
thread_interval = 30.0  # seconds to sleep between checks
thread_started = False
params_file = "/data/cp_params.json"
variables_written = []
read_params()
last_params = copy.deepcopy(params)
