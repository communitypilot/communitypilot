import zmq
from selfdrive.services import service_list
import selfdrive.messaging as messaging

class PhantomReceiver():
  def __init__(self):
    self.phantomData_sock = None

  def broadcast_data(self, status, speed, angle, time):
    status = True if status == "true" or status is True else False
    data = messaging.new_message()
    data.init('phantomData')
    data.phantomData.status = status
    data.phantomData.speed = speed
    data.phantomData.angle = angle
    data.phantomData.time = time
    self.phantomData_sock.send(data.to_bytes())

  def open_socket(self):
    self.phantomData_sock = messaging.pub_sock(zmq.Context(), service_list['phantomData'].port)

  def close_socket(self):
    self.phantomData_sock.close()
