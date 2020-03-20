#include <trafficd.h>
#include <cassert>
#include <iostream>
using namespace std;

volatile sig_atomic_t do_exit = 0;
int main(){
	VisionStream stream;
	Context* c = Context::create();
    PubSocket* traffic_lights_sock = PubSocket::create(c, "rawtraffic");
    assert(traffic_lights_sock != NULL);
	while (!do_exit){  
        VisionStreamBufs buf_info;
        int err = visionstream_init(&stream, VISION_STREAM_YUV, true, &buf_info);
        if (err != 0) {
            printf("trafficd: visionstream fail\n");
            usleep(10000);
		}
		VIPCBuf* buf;
            VIPCBufExtra extra;
		buf = visionstream_get(&stream, &extra);
            if (buf == NULL) {
                printf("trafficd: visionstream  failed\n");
                break;
            }
            else {
                cout << buf << endl;
            }
		}


}
