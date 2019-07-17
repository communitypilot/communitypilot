import copy
from common.kalman.simple_kalman import KF1D
from selfdrive.car.modules.UIBT_module import UIButtons,UIButton
from selfdrive.car.modules.UIEV_module import UIEvents
from selfdrive.config import Conversions as CV
from selfdrive.can.parser import CANParser
import selfdrive.kegman_conf as kegman
from selfdrive.car.subaru.values import CAR, DBC, STEER_THRESHOLD

def get_powertrain_can_parser(CP):
  # this function generates lists for signal, messages and initial values
  signals = [
    # sig_name, sig_address, default
    ("Steer_Torque_Sensor", "Steering_Torque", 0),
    ("Steering_Angle", "Steering_Torque", 0),
    ("Steer_Torque_Output", "Steering_Torque", 0),
    ("Cruise_On", "CruiseControl", 0),
    ("Cruise_Activated", "CruiseControl", 0),
    ("Brake_Pedal", "Brake_Pedal", 0),
    ("Throttle_Pedal", "Throttle", 0),
    ("LEFT_BLINKER", "Dashlights", 0),
    ("RIGHT_BLINKER", "Dashlights", 0),
    ("SEATBELT_FL", "Dashlights", 0),
    
    ("FL", "Wheel_Speeds", 0),
    ("FR", "Wheel_Speeds", 0),
    ("RL", "Wheel_Speeds", 0),
    ("RR", "Wheel_Speeds", 0),
    ("DOOR_OPEN_FR", "BodyInfo", 1),
    ("DOOR_OPEN_FL", "BodyInfo", 1),
    ("DOOR_OPEN_RR", "BodyInfo", 1),
    ("DOOR_OPEN_RL", "BodyInfo", 1),
    ("Units", "Dash_State", 1),
  ]

  checks = [
    # sig_address, frequency
    ("Dashlights", 10),
    ("Wheel_Speeds", 50),
    ("Steering_Torque", 50),
  ]
  
  if CP.carFingerprint not in (CAR.OUTBACK, CAR.LEGACY):
    checks += [
      ("BodyInfo", 10),
      ("CruiseControl", 20),
    ]

  else:
    signals += [
      ("LKA_Lockout", "Steering_Torque", 0),
    ]
    checks += [
      ("CruiseControl", 50),
    ]


  return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, 0)

def get_camera_can_parser(CP):
  signals = [
    ("Cruise_Set_Speed", "ES_DashStatus", 0),
  ]

  checks = [
    ("ES_DashStatus", 10),
  ]

  if CP.carFingerprint not in (CAR.OUTBACK, CAR.LEGACY):
    signals += [
      ("Counter", "ES_Distance", 0),
      ("Signal1", "ES_Distance", 0),
      ("Signal2", "ES_Distance", 0),
      ("Main", "ES_Distance", 0),
      ("Signal3", "ES_Distance", 0),

      ("Checksum", "ES_LKAS_State", 0),
      ("Counter", "ES_LKAS_State", 0),
      ("Keep_Hands_On_Wheel", "ES_LKAS_State", 0),
      ("Empty_Box", "ES_LKAS_State", 0),
      ("Signal1", "ES_LKAS_State", 0),
      ("LKAS_ACTIVE", "ES_LKAS_State", 0),
      ("Signal2", "ES_LKAS_State", 0),
      ("Backward_Speed_Limit_Menu", "ES_LKAS_State", 0),
      ("LKAS_ENABLE_3", "ES_LKAS_State", 0),
      ("Signal3", "ES_LKAS_State", 0),
      ("LKAS_ENABLE_2", "ES_LKAS_State", 0),
      ("Signal4", "ES_LKAS_State", 0),
      ("FCW_Cont_Beep", "ES_LKAS_State", 0),
      ("FCW_Repeated_Beep", "ES_LKAS_State", 0),
      ("Throttle_Management_Activated", "ES_LKAS_State", 0),
      ("Traffic_light_Ahead", "ES_LKAS_State", 0),
      ("Right_Depart", "ES_LKAS_State", 0),
      ("Signal5", "ES_LKAS_State", 0),
    ]

  return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, 1)

class CarState(object):
  def __init__(self, CP):
    self.gasMode = int(kegman.conf['lastGasMode'])
    self.gasLabels = ["dynamic","sport","eco"]
    self.alcaLabels = ["MadMax","Normal","Wifey","off"]
    self.alcaMode = int(kegman.conf['lastALCAMode'])
    steerRatio = CP.steerRatio
    self.prev_distance_button = 0
    self.distance_button = 0
    self.prev_lka_button = 0
    self.lka_button = 0
    self.lkMode = True
    self.lane_departure_toggle_on = True
    # ALCA PARAMS
    self.blind_spot_on = bool(0)
    # max REAL delta angle for correction vs actuator
    self.CL_MAX_ANGLE_DELTA_BP = [10., 32., 55.]
    self.CL_MAX_ANGLE_DELTA = [0.77 * 16.2 / steerRatio, 0.86 * 16.2 / steerRatio, 0.535 * 16.2 / steerRatio]
    # adjustment factor for merging steer angle to actuator; should be over 4; the higher the smoother
    self.CL_ADJUST_FACTOR_BP = [10., 44.]
    self.CL_ADJUST_FACTOR = [16. , 8.]
    # reenrey angle when to let go
    self.CL_REENTRY_ANGLE_BP = [10., 44.]
    self.CL_REENTRY_ANGLE = [5. , 5.]
    # a jump in angle above the CL_LANE_DETECT_FACTOR means we crossed the line
    self.CL_LANE_DETECT_BP = [10., 44.]
    self.CL_LANE_DETECT_FACTOR = [1.5, 2.5]
    self.CL_LANE_PASS_BP = [10., 20., 44.]
    self.CL_LANE_PASS_TIME = [40.,10., 4.] 
    # change lane delta angles and other params
    self.CL_MAXD_BP = [10., 32., 44.]
    self.CL_MAXD_A = [.358, 0.084, 0.040] #delta angle based on speed; needs fine tune, based on Tesla steer ratio of 16.75
    self.CL_MIN_V = 8.9 # do not turn if speed less than x m/2; 20 mph = 8.9 m/s
    # do not turn if actuator wants more than x deg for going straight; this should be interp based on speed
    self.CL_MAX_A_BP = [10., 44.]
    self.CL_MAX_A = [10., 10.] 
    # define limits for angle change every 0.1 s
    # we need to force correction above 10 deg but less than 20
    # anything more means we are going to steep or not enough in a turn
    self.CL_MAX_ACTUATOR_DELTA = 2.
    self.CL_MIN_ACTUATOR_DELTA = 0. 
    self.CL_CORRECTION_FACTOR = [1.,1.1,1.2]
    self.CL_CORRECTION_FACTOR_BP = [10., 32., 44.]
    #duration after we cross the line until we release is a factor of speed
    self.CL_TIMEA_BP = [10., 32., 44.]
    self.CL_TIMEA_T = [0.2 ,0.2, 0.2]
    #duration to wait (in seconds) with blinkers on before starting to turn
    self.CL_WAIT_BEFORE_START = 1
    #END OF ALCA PARAMS
    
    # initialize can parser
    self.CP = CP

    #BB UIEvents
    self.UE = UIEvents(self)
    
    #BB variable for custom buttons
    self.cstm_btns = UIButtons(self,"Subaru","subaru")

    #BB pid holder for ALCA
    self.pid = None

    #BB custom message counter
    self.custom_alert_counter = -1 #set to 100 for 1 second display; carcontroller will take down to zero
    
    self.car_fingerprint = CP.carFingerprint
    self.left_blinker_on = False
    self.prev_left_blinker_on = False
    self.right_blinker_on = False
    self.prev_right_blinker_on = False
    self.steer_torque_driver = 0
    self.steer_not_allowed = False
    self.main_on = False

    # vEgo kalman filter
    dt = 0.01
    self.v_ego_kf = KF1D(x0=[[0.], [0.]],
                         A=[[1., dt], [0., 1.]],
                         C=[1., 0.],
                         K=[[0.12287673], [0.29666309]])
    self.v_ego = 0.
   #BB init ui buttons
  def init_ui_buttons(self):
    btns = []
    btns.append(UIButton("sound", "SND", 0, "", 0))
    btns.append(UIButton("alca", "ALC", 0, self.alcaLabels[self.alcaMode], 1))
    btns.append(UIButton("mad","MAD",0,"",2))
    btns.append(UIButton("","",0,"",3))
    btns.append(UIButton("gas","GAS",1,self.gasLabels[self.gasMode],4))
    btns.append(UIButton("lka","LKA",1,"",5))
    return btns
  #BB update ui buttons
  def update_ui_buttons(self,id,btn_status):
    if self.cstm_btns.btns[id].btn_status > 0:
      if (id == 1) and (btn_status == 0) and self.cstm_btns.btns[id].btn_name=="alca":
          if self.cstm_btns.btns[id].btn_label2 == self.alcaLabels[self.alcaMode]:
            self.alcaMode = (self.alcaMode + 1 ) % 4
            kegman.save({'lastALCAMode': int(self.alcaMode)})  # write last distance bar setting to file
          else:
            self.alcaMode = 0
            kegman.save({'lastALCAMode': int(self.alcaMode)})  # write last distance bar setting to file
          self.cstm_btns.btns[id].btn_label2 = self.alcaLabels[self.alcaMode]
          self.cstm_btns.hasChanges = True
          if self.alcaMode == 3:
            self.cstm_btns.set_button_status("alca", 0)
      elif (id == 4) and (btn_status == 0) and self.cstm_btns.btns[id].btn_name=="gas":
          if self.cstm_btns.btns[id].btn_label2 == self.gasLabels[self.gasMode]:
            self.gasMode = (self.gasMode + 1 ) % 3
            kegman.save({'lastGasMode': int(self.gasMode)})  # write last GasMode setting to file
          else:
            self.gasMode = 0
            kegman.save({'lastGasMode': int(self.gasMode)})  # write last GasMode setting to file
          self.cstm_btns.btns[id].btn_label2 = self.gasLabels[self.gasMode]
          self.cstm_btns.hasChanges = True
      else:
        self.cstm_btns.btns[id].btn_status = btn_status * self.cstm_btns.btns[id].btn_status
    else:
        self.cstm_btns.btns[id].btn_status = btn_status
        if (id == 1) and self.cstm_btns.btns[id].btn_name=="alca":
          self.alcaMode = (self.alcaMode + 1 ) % 4
          kegman.save({'lastALCAMode': int(self.alcaMode)})  # write last distance bar setting to file
          self.cstm_btns.btns[id].btn_label2 = self.alcaLabels[self.alcaMode]
          self.cstm_btns.hasChanges = True
          
  def update(self, cp, cp_cam):

    self.can_valid = cp.can_valid
    self.cam_can_valid = cp_cam.can_valid

    self.pedal_gas = cp.vl["Throttle"]['Throttle_Pedal']
    self.brake_pressure = cp.vl["Brake_Pedal"]['Brake_Pedal']
    self.user_gas_pressed = self.pedal_gas > 0
    self.brake_pressed = self.brake_pressure > 0
    self.brake_lights = bool(self.brake_pressed)

    self.v_wheel_fl = cp.vl["Wheel_Speeds"]['FL'] * CV.KPH_TO_MS
    self.v_wheel_fr = cp.vl["Wheel_Speeds"]['FR'] * CV.KPH_TO_MS
    self.v_wheel_rl = cp.vl["Wheel_Speeds"]['RL'] * CV.KPH_TO_MS
    self.v_wheel_rr = cp.vl["Wheel_Speeds"]['RR'] * CV.KPH_TO_MS

    self.v_cruise_pcm = cp_cam.vl["ES_DashStatus"]['Cruise_Set_Speed']
    # 1 = imperial, 6 = metric
    if cp.vl["Dash_State"]['Units'] == 1:
      self.v_cruise_pcm *= CV.MPH_TO_KPH

    v_wheel = (self.v_wheel_fl + self.v_wheel_fr + self.v_wheel_rl + self.v_wheel_rr) / 4.
    # Kalman filter, even though Subaru raw wheel speed is heaviliy filtered by default
    if abs(v_wheel - self.v_ego) > 2.0:  # Prevent large accelerations when car starts at non zero speed
      self.v_ego_kf.x = [[v_wheel], [0.0]]

    self.v_ego_raw = v_wheel
    v_ego_x = self.v_ego_kf.update(v_wheel)

    self.v_ego = float(v_ego_x[0])
    self.a_ego = float(v_ego_x[1])
    self.standstill = self.v_ego_raw < 0.01

    self.prev_left_blinker_on = self.left_blinker_on
    self.prev_right_blinker_on = self.right_blinker_on
    self.left_blinker_on = cp.vl["Dashlights"]['LEFT_BLINKER'] == 1
    self.right_blinker_on = cp.vl["Dashlights"]['RIGHT_BLINKER'] == 1
    self.seatbelt_unlatched = cp.vl["Dashlights"]['SEATBELT_FL'] == 1
    self.steer_torque_driver = cp.vl["Steering_Torque"]['Steer_Torque_Sensor']
    self.steer_torque_motor = cp.vl["Steering_Torque"]['Steer_Torque_Output']
    self.acc_active = cp.vl["CruiseControl"]['Cruise_Activated']
    self.main_on = cp.vl["CruiseControl"]['Cruise_On']
    self.steer_override = abs(self.steer_torque_driver) > STEER_THRESHOLD[self.car_fingerprint]
    self.angle_steers = cp.vl["Steering_Torque"]['Steering_Angle']
    self.door_open = any([cp.vl["BodyInfo"]['DOOR_OPEN_RR'],
      cp.vl["BodyInfo"]['DOOR_OPEN_RL'],
      cp.vl["BodyInfo"]['DOOR_OPEN_FR'],
      cp.vl["BodyInfo"]['DOOR_OPEN_FL']])

    self.es_distance_msg = copy.copy(cp_cam.vl["ES_Distance"])
    self.es_lkas_msg = copy.copy(cp_cam.vl["ES_LKAS_State"])
    
    if self.car_fingerprint not in (CAR.OUTBACK, CAR.LEGACY):
      self.v_cruise_pcm = cp_cam.vl["ES_DashStatus"]["Cruise_Set_Speed"] * CV.MPH_TO_KPH
      self.es_distance_msg = copy.copy(cp_cam.vl["ES_Distance"])
      self.es_lkas_msg = copy.copy(cp_cam.vl["ES_LKAS_State"])
    else:
      self.v_cruise_pcm = cp_cam.vl["ES_DashStatus"]["Cruise_Set_Speed"]
      self.steer_not_allowed = cp.vl["Steering_Torque"]["LKA_Lockout"]
    
    if self.cstm_btns.get_button_status("lka") == 0:
      self.lane_departure_toggle_on = False
    else:
      if self.alcaMode == 3 and (self.left_blinker_on or self.right_blinker_on):
        self.lane_departure_toggle_on = False
      else:
        self.lane_departure_toggle_on = True
