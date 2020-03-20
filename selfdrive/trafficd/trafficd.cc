#include <cstdlib>
#include <unistd.h>
#include <ctime>
#include <iostream>
#include "common/visionbuf.h"
#include "common/visionipc.h"

#include "svpng.inc"
using namespace std;
int main() {
  VisionStream stream;

  VisionStreamBufs buf_info;
  while (true) {
    int err = visionstream_init(&stream, VISION_STREAM_YUV, true, &buf_info);
    if (err != 0) {
      printf("visionstream fail\n");
      usleep(100000);
    }
    break;
  }
  while(true){
  VIPCBufExtra extra;
  VIPCBuf* buf = visionstream_get(&stream, &extra);
  if (buf == NULL) {
    printf("visionstream get failed\n");
    return 1;
  }

  int width = buf_info.width;
  int height = buf_info.height;

  uint8_t *y = (uint8_t *)buf->addr;
  uint8_t *u = y + (width * height);
  uint8_t *v = u + ((width * height) / 4);

  int r, g, b;
  uint8_t* rgb = (uint8_t*)calloc((width * height * 3), sizeof(uint8_t));
  uint8_t* rgb_ptr = rgb;

  for (int j = 0; j < height; j++) {
    for (int i = 0; i < width; i++) {
      int yy = y[(j * width) + i];
      int uu = u[((j / 2) * (width / 2)) + (i / 2)];
      int vv = v[((j / 2) * (width / 2)) + (i / 2)];

      *rgb_ptr++ = 1.164 * (yy - 16) + 1.596 * (vv - 128);
      *rgb_ptr++ = 1.164 * (yy - 16) - 0.813 * (vv - 128) - 0.391 * (uu - 128);
      *rgb_ptr++ = 1.164 * (yy - 16) + 2.018 * (uu - 128);
    }
  }

  time_t curr_time = time(NULL);
	tm * curr_tm = localtime(&curr_time);
  char timestamp[14];
  char filename[22];
  strftime(timestamp, 15, "%Y%m%d%H%M%S", curr_tm);
  sprintf(filename, "%s.png", timestamp);

  FILE *fp = fopen(filename, "wb");
  svpng(fp, width, height, rgb, 0);
  fclose(fp);
  usleep(40 *10);
  cout << "New image" << endl;
  } 

  return 0;
}