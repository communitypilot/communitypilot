#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <unistd.h>

#include <zmq.h>

#include "common/visionipc.h"
#include "common/timing.h"

int main() {
  int err;
  double t1 = millis_since_boot();
  VisionStream stream;

  VisionStreamBufs buf_info;
  while (true) {
    err = visionstream_init(&stream, VISION_STREAM_RGB_BACK, true, &buf_info);
    if (err != 0) {
      printf("visionstream fail\n");
      usleep(100000);
    }
    break;
  }

  VIPCBufExtra extra;
  VIPCBuf* buf = visionstream_get(&stream, &extra);
  if (buf == NULL) {
    printf("visionstream get failed\n");
    return 1;
  }

  double t2 = millis_since_boot();

  printf("fetch time:   %.2f\n", (t2-t1));

  //int image_width = 1164;
  //int image_height = 874;
  //int image_stride = 3840;
  //int padding = 348;

  //void* img = malloc(image_height * image_width * 3);
  void* img = malloc(3052008);
  uint8_t *dst_ptr = (uint8_t *)img;
  uint8_t *src_ptr = (uint8_t *)buf->addr;

  // 1280 stride 116 padding
  for(int line=0;line<=874;line++) {
    for(int line_pos=0;line_pos<=3492;line_pos+=3) {
      dst_ptr[line_pos + 0] = src_ptr[line_pos + 2];
      dst_ptr[line_pos + 1] = src_ptr[line_pos + 1];
      dst_ptr[line_pos + 2] = src_ptr[line_pos + 0];
    }
    dst_ptr += 3492;
    src_ptr += 3840;
  }

  double t3 = millis_since_boot();

  printf("process time: %.2f\n", (t3-t2));

  FILE *f = fopen("./test", "wb");
  fwrite((uint8_t *)img, 1, 3052008, f);
  free(img);
  fclose(f);

  double t4 = millis_since_boot();

  printf("write time:   %.2f\n", (t4-t3));

  visionstream_destroy(&stream);

  double t5 = millis_since_boot();

  printf("total time:   %.2f\n", (t5-t1));

  return 0;
}