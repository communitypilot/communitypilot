import ftplib
import sys
import os
import argparse


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
  upload_to_ftp('dongle_id', 'logname/fcamera.hevc', '/data/test.txt')


