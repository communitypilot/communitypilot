#include <time.h>
//#include <dirent.h>

#define DASH_STATE_NONE 0
#define DASH_STATE_CAPTURING 1
#define DASH_STATE_NOT_CAPTURING 2
#define DASH_STATE_PAUSED 3
#define CLICK_INT 0.2

typedef struct dashboard_element {
  int pos_x;
  int pos_y;
  int width;
  int height;
} dashboard_element;

dashboard_element dash_button;

int dashState = DASH_STATE_NOT_CAPTURING;
int dashNum = 0;
int start_timed = 0;
int elapsed_timed = 0; // Time of current recording
int click_elapsed_timed = 0;
int click_int = 0;
int dash_image; // Stores reference to the PNG

bool lock_current_dash = false;

int getTime() {
  // Get current time (in seconds)

  int iRet;
  struct timeval tv;
  int seconds = 0;

  iRet = gettimeofday(&tv,NULL);
  if (iRet == 0) {
    seconds = (int)tv.tv_sec;
  }
  return seconds;
}

struct tm getTimeStruct() {
  time_t t = time(NULL);
  struct tm tm = *localtime(&t);
  return tm;
}

bool screenLockButton_clicked(int touch_x, int touch_y, dashboard_element el) {
  if (dashState == DASH_STATE_NOT_CAPTURING) {
    // Don't register click if we're not running
    return false;
  }

  if (touch_x >= el.pos_x && touch_x <= el.pos_x + el.width) {
    if (touch_y >= el.pos_y && touch_y <= el.pos_y + el.height) {
      return true;
    }
  }
  return false;
}

bool screenButton_clicked(int touch_x, int touch_y) {
  if (touch_x >= 1660 && touch_x <= 1810) {
    if (touch_y >= 785 && touch_y <= 935) {
      return true;
    }
  }
  return false;
}

void drawLock_button(UIState *s) {
  int btn_w = 150;
  int btn_h = 150;
  int btn_x = 1920 - btn_w - 150;
  int btn_y = 1080 - btn_h;
  int imgw, imgh;
  float alpha = 0.3f;

  if (!dash_image) {
    // Load the lock icon
    dash_image = nvgCreateImage(s->vg, "../assets/img_dashboard.png", 1);
  }

  if (lock_current_dash) {
    alpha = 1.0f;
  }

  nvgBeginPath(s->vg);
  NVGpaint imgPaint = nvgImagePattern(s->vg, btn_x-125, btn_y-200, 150, 150, 0, dash_image, alpha);
  nvgRoundedRect(s->vg, btn_x-125, btn_y-200, 150, 150, 100);
  nvgFillPaint(s->vg, imgPaint);
  nvgFill(s->vg);


  dash_button = (dashboard_element){
    .pos_x = 1500,
    .pos_y = 1120,
    .width = 150,
    .height = 150
  };
}

void startDash() {
  dashState = DASH_STATE_CAPTURING;
  start_timed = getTime();
  system("tmux new -d -s dashboard 'cd /data/openpilot ; python dashboard.py'");
}

void stopDash() {
  if (dashState == DASH_STATE_CAPTURING) {
    system("tmux kill-session -t dashboard");
    dashState = DASH_STATE_NOT_CAPTURING;
    elapsed_timed = getTime() - start_timed;
  }
}

void screenToggle_lock() {
  if (lock_current_dash) {
    lock_current_dash = false;
  }
  else {
    lock_current_dash = true;
  }
}

static void screenDraw_button(UIState *s, int touch_x, int touch_y) {
  // Set button to bottom left of screen
  if (s->vision_connected && s->plus_state == 0) {

    if (dashState == DASH_STATE_CAPTURING) {
      drawLock_button(s);
    }

    int btn_w = 150;
    int btn_h = 150;
    int btn_x = 1920 - btn_w;
    int btn_y = 1080 - btn_h;
    nvgBeginPath(s->vg);
      nvgRoundedRect(s->vg, btn_x-110, btn_y-200, btn_w, btn_h, 100);
      nvgStrokeColor(s->vg, nvgRGBA(255,255,255,80));
      nvgStrokeWidth(s->vg, 6);
      nvgStroke(s->vg);

      nvgFontSize(s->vg, 70);

      if (dashState == DASH_STATE_CAPTURING) {
        NVGcolor fillColor = nvgRGBA(255,0,0,150);
        nvgFillColor(s->vg, fillColor);
        nvgFill(s->vg);
        nvgFillColor(s->vg, nvgRGBA(255,255,255,200));
      } else {
      nvgFillColor(s->vg, nvgRGBA(255, 255, 255, 200));
      }
      nvgText(s->vg,btn_x-88,btn_y-105,"DBG",NULL);
  }

  if (dashState == DASH_STATE_CAPTURING) {

    elapsed_timed = getTime() - start_timed;

  }
}

void screenToggle_dash_state() {
  if (dashState == DASH_STATE_CAPTURING) {
    stopDash();
    lock_current_dash = false;
  }
  else {
    dashState = DASH_STATE_CAPTURING;
    startDash();
  }
}

void dashboard( UIState *s, int touch_x, int touch_y ) {
  screenDraw_button(s, touch_x, touch_y);
  if (screenButton_clicked(touch_x,touch_y)) {
    click_elapsed_timed = getTime() - click_int;

    if (click_elapsed_timed > 0) {
      click_int = getTime() + 1;
      screenToggle_dash_state();
    }
  }

  if (screenLockButton_clicked(touch_x,touch_y,dash_button)) {
    screenToggle_lock();
  }
  if (!s->vision_connected) {
    // Assume car is not in drive so stop running dashboard
    stopDash();
  }
  if (s->scene.v_ego > 3.1 && dashState == DASH_STATE_PAUSED) {
    startDash();
  } /*else if (s->scene.v_ego < 2.9 && dashState == DASH_STATE_CAPTURING) {
    stopDash();
    dashState = DASH_STATE_PAUSED;
  }*/
  s->scene.recordDash = (dashState != DASH_STATE_NOT_CAPTURING);
}
