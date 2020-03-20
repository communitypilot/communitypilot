import cereal.messaging as messaging

# in subscriber
sm = messaging.SubMaster(['frame'])
while 1:
  sm.update()
  print(sm['frame'])