import ftplib
import sys
import os
import argparse
import selfdrive.cp_params as cp_params
import random
import string
import json

def upload_df_data():
  filepath = "/data/openpilot/selfdrive/data_collection/df-data"
  if os.path.isfile(filepath):
    if cp_params.get("uniqueID") is None:
      cp_params.save({"uniqueID": ''.join([random.choice(string.lowercase+string.uppercase+string.digits) for i in range(15)])})
    try:
      username = cp_params.get("uniqueID", ''.join([random.choice(string.lowercase+string.uppercase+string.digits) for i in range(15)]))
      try:
        with open("/data/data/ai.comma.plus.offroad/files/persistStore/persist-auth", "r") as f:
          auth = json.loads(f.read())
        auth = json.loads(auth['commaUser'])
        if auth and str(auth['username']) != "":
          username = str(auth['username'])
      except:
        pass

      username += "-{}".format(cp_params.get('userCar', default=''))

      filename = "df-data.{}".format(random.randint(1,99999))

      ftp = ftplib.FTP("smiskol.com")
      ftp.login("eon", "87pYEYF4vFpwvgXU")
      with open(filepath, "rb") as f:
        try:
          ftp.mkd("/{}".format(username))
        except:
          pass
        ftp.storbinary("STOR /{}/{}".format(username, filename), f)
      ftp.quit()
      os.remove(filepath)
      return True
    except:
      return False
  else:
    return False


def get_arg_parser():
  parser = argparse.ArgumentParser(
    description="Upload to ftp server",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument("file_path", nargs='?', default="/data/test.txt",
                        help="Path to the file")
  return parser


def cd_dir_and_auto_create(ftp, currentDir):
  if currentDir != "":
    try:
      ftp.cwd(currentDir)
    except:
      cd_dir_and_auto_create(ftp, "/".join(currentDir.split("/")[:-1]))
      ftp.mkd(currentDir)
      ftp.cwd(currentDir)

def upload_to_ftp(dongle_id, key, file_path):
  #print('ftp: {}, {}, {}'.format(dongle_id, key, file_path))
  ftp = ftplib.FTP("kevo.live")
  ftp.login("openpilot", "openpilotdf")
  with open(file_path, 'rb') as f:
    remote_dir = os.path.join('/Home', dongle_id, os.path.dirname(key))
    cd_dir_and_auto_create(ftp, remote_dir)
    ftp.storbinary('STOR ' + os.path.basename(file_path), f)
  ftp.quit()


if __name__ == "__main__":
  args = get_arg_parser().parse_args(sys.argv[1:])
  upload_df_data()
  upload_to_ftp('dongle_id', 'logname/fcamera.hevc', '/data/test.txt')


