#from common.numpy_fast import clip
from common.realtime import sec_since_boot
from selfdrive.boardd.boardd import can_list_to_can_capnp
from selfdrive.car import apply_std_steer_torque_limits
from selfdrive.car.subaru import subarucan
from selfdrive.car.subaru.values import CAR, DBC
from selfdrive.can.packer import CANPacker

from selfdrive.car.modules.ALCA_module import ALCAController

class CarControllerParams():
  def __init__(self, car_fingerprint):
    self.STEER_MAX = 2047              # max_steer 4095
    self.STEER_STEP = 2                # how often we update the steer cmd
    self.STEER_DELTA_UP = 50           # torque increase per refresh, 0.8s to max
    self.STEER_DELTA_DOWN = 70         # torque decrease per refresh
    if car_fingerprint == (CAR.IMPREZA, CAR.XV):
      self.STEER_DRIVER_ALLOWANCE = 60   # allowed driver torque before start limiting
      self.STEER_DRIVER_MULTIPLIER = 10   # weight driver torque heavily
      self.STEER_DRIVER_FACTOR = 1     # from dbc
    if car_fingerprint in (CAR.OUTBACK, CAR.LEGACY):
      self.STEER_DRIVER_ALLOWANCE = 300   # allowed driver torque before start limiting
      self.STEER_DRIVER_MULTIPLIER = 1   # weight driver torque heavily
      self.STEER_DRIVER_FACTOR = 1     # from dbc
      self.STEER_DELTA_DOWN = 60         # torque decrease per refresh


class CarController(object):
  def __init__(self, car_fingerprint):
    self.start_time = sec_since_boot()
    self.lkas_active = False
    self.steer_idx = 0
    self.apply_steer_last = 0
    self.car_fingerprint = car_fingerprint
    self.es_distance_cnt = -1
    self.es_lkas_cnt = -1
    self.counter = 0
    
    self.ALCA = ALCAController(self,True,False) # Enabled  True and SteerByAngle only False
    
    # Setup detection helper. Routes commands to
    # an appropriate CAN bus number.
    self.params = CarControllerParams(car_fingerprint)
    print(DBC)
    self.packer = CANPacker(DBC[car_fingerprint]['pt'])

  def update(self, sendcan, enabled, CS, frame, actuators, pcm_cancel_cmd, visual_alert):
    #update custom UI buttons and alerts
    CS.UE.update_custom_ui()
    if (frame % 1000 == 0):
      CS.cstm_btns.send_button_info()
      CS.UE.uiSetCarEvent(CS.cstm_btns.car_folder,CS.cstm_btns.car_name)

    # Get the angle from ALCA.
    alca_enabled = False
    alca_steer = 0.
    alca_angle = 0.
    turn_signal_needed = 0
    # Update ALCA status and custom button every 0.1 sec.
    if self.ALCA.pid == None:
      self.ALCA.set_pid(CS)
    if (frame % 10 == 0):
      self.ALCA.update_status(CS.cstm_btns.get_button_status("alca") > 0)
    # steer torque
    alca_angle, alca_steer, alca_enabled, turn_signal_needed = self.ALCA.update(enabled, CS, frame, actuators)
    """ Controls thread """

    P = self.params

    # Send CAN commands.
    can_sends = []

    ### STEER ###

    if (frame % P.STEER_STEP) == 0:

      final_steer = alca_steer if enabled else 0.
      apply_steer = int(round(final_steer * P.STEER_MAX))

      # limits due to driver torque

      apply_steer = int(round(apply_steer))
      apply_steer = apply_std_steer_torque_limits(apply_steer, self.apply_steer_last, CS.steer_torque_driver, P)

      lkas_enabled = enabled and not CS.steer_not_allowed

      if not lkas_enabled:
        apply_steer = 0
        
      if self.car_fingerprint in (CAR.OUTBACK, CAR.LEGACY):

        # add noise to prevent lkas fault from constant torque value over 1s
        if enabled and apply_steer == self.apply_steer_last:
          self.counter =+ 1
          if self.counter == 50:
            apply_steer = round(int(apply_steer * 0.99))
        else:
          self.counter = 0

      can_sends.append(subarucan.create_steering_control(self.packer, CS.CP.carFingerprint, apply_steer, frame, P.STEER_STEP))

      self.apply_steer_last = apply_steer

    if self.car_fingerprint not in (CAR.OUTBACK, CAR.LEGACY):

      if self.es_distance_cnt != CS.es_distance_msg["Counter"]:
        can_sends.append(subarucan.create_es_distance(self.packer, CS.es_distance_msg, pcm_cancel_cmd))
        self.es_distance_cnt = CS.es_distance_msg["Counter"]

      if self.es_lkas_cnt != CS.es_lkas_msg["Counter"]:
        can_sends.append(subarucan.create_es_lkas(self.packer, CS.es_lkas_msg, visual_alert))
        self.es_lkas_cnt = CS.es_lkas_msg["Counter"]

    if self.car_fingerprint in (CAR.OUTBACK, CAR.LEGACY) and pcm_cancel_cmd:
      can_sends.append(subarucan.create_door_control(self.packer))

    sendcan.send(can_list_to_can_capnp(can_sends, msgtype='sendcan'))
