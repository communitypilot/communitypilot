import urllib
import os
import time

apk_dir="/data/communitypilot_scripts"
install_script = "https://raw.githubusercontent.com/pjlao307/communitypilot-apk-dist/master/install.py"

def checkConnection():
  try:
    url = "https://raw.githubusercontent.com/pjlao307/communitypilot-apk-dist/master/install.py"
    urllib.urlopen(url)
    isConnected = True
  except:
    isConnected = False

  return isConnected

def waitForConnection():
  isConnected = False
  connectCount = 0 
  maxWaitTime = 10  

  while not isConnected:
    print "Waitng for internet connection"
    if connectCount >= maxWaitTime:
      break
    connectCount += 1
    isConnected = checkConnection()
    time.sleep(1)

  if not isConnected:
    print "No connection, giving up"
    exit

print "Checking for custom APK installation"
path_exists = os.path.isdir(apk_dir)

if not path_exists:
  print "%s does not exist, installing" % apk_dir
  waitForConnection()
  os.system("curl -L %s | python" % install_script)
else:
  print "APK already installed"
