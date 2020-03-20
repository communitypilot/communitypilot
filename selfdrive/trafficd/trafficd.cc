#include "trafficd.h"
#include <cassert>
#include <iostream>
#include <iostream>
#include <chrono>
#include <thread>

#include <highgui.h>

#include "cereal/gen/cpp/log.capnp.h"
#include <capnp/message.h>
#include <capnp/serialize.h>
#include <kj/array.h>
#include <kj/io.h>

#include "messaging.hpp"
using namespace std;

std::unique_ptr<zdl::SNPE::SNPE> snpe;
volatile sig_atomic_t do_exit = 0;

const std::vector<std::string> modelLabels = {"RED", "GREEN", "YELLOW", "NONE"};
const double modelRate = 1 / 5.;  // 5 Hz

const int original_shape[3] = {874, 1164, 3};   // global constants
const int original_size = 874 * 1164 * 3;
const int cropped_shape[3] = {665, 814, 3};
const int cropped_size = 665 * 814 * 3;

const int horizontal_crop = 175;
const int top_crop = 0;
const int hood_crop = 209;
const double msToSec = 1 / 1000.;  // multiply
const double secToUs = 1e+6;

zdl::DlSystem::Runtime_t checkRuntime() {
    static zdl::DlSystem::Version_t Version = zdl::SNPE::SNPEFactory::getLibraryVersion();
    static zdl::DlSystem::Runtime_t Runtime;
    std::cout << "SNPE Version: " << Version.asString().c_str() << std::endl; //Print Version number
    if (zdl::SNPE::SNPEFactory::isRuntimeAvailable(zdl::DlSystem::Runtime_t::GPU)) {
        Runtime = zdl::DlSystem::Runtime_t::GPU;  // todo: using CPU
    } else {
        Runtime = zdl::DlSystem::Runtime_t::CPU;
    }
    return Runtime;
}

void initializeSNPE(zdl::DlSystem::Runtime_t runtime) {
    std::unique_ptr<zdl::DlContainer::IDlContainer> container;
    container = zdl::DlContainer::IDlContainer::open("../../models/traffic_model.dlc");
    zdl::SNPE::SNPEBuilder snpeBuilder(container.get());
    snpe = snpeBuilder.setOutputLayers({})
                      .setRuntimeProcessor(runtime)
                      .setUseUserSuppliedBuffers(false)
                      .setPerformanceProfile(zdl::DlSystem::PerformanceProfile_t::HIGH_PERFORMANCE)
                      .setCPUFallbackMode(true)
                      .build();
}

std::unique_ptr<zdl::DlSystem::ITensor> loadInputTensor(std::unique_ptr<zdl::SNPE::SNPE> &snpe, std::vector<float> inputVec) {
    std::unique_ptr<zdl::DlSystem::ITensor> input;
    const auto &strList_opt = snpe->getInputTensorNames();

    if (!strList_opt) throw std::runtime_error("Error obtaining Input tensor names");
    const auto &strList = *strList_opt;
    assert (strList.size() == 1);

    const auto &inputDims_opt = snpe->getInputDimensions(strList.at(0));
    const auto &inputShape = *inputDims_opt;

    input = zdl::SNPE::SNPEFactory::getTensorFactory().createTensor(inputShape);

    /* Copy the loaded input file contents into the networks input tensor. SNPE's ITensor supports C++ STL functions like std::copy() */
    std::copy(inputVec.begin(), inputVec.end(), input->begin());
    return input;
}

zdl::DlSystem::ITensor* executeNetwork(std::unique_ptr<zdl::SNPE::SNPE>& snpe, std::unique_ptr<zdl::DlSystem::ITensor>& input) {
    static zdl::DlSystem::TensorMap outputTensorMap;
    snpe->execute(input.get(), outputTensorMap);
    zdl::DlSystem::StringList tensorNames = outputTensorMap.getTensorNames();

    const char* name = tensorNames.at(0);  // only should the first
    auto tensorPtr = outputTensorMap.getTensor(name);
    return tensorPtr;
}

void setModelOutput(const zdl::DlSystem::ITensor* tensor, float* outputArray) {
    int counter = 0;
    for (auto it = tensor->cbegin(); it != tensor->cend(); ++it ){
        float op = *it;
        outputArray[counter] = op;
        counter += 1;
    }
}

void initModel() {
    zdl::DlSystem::Runtime_t runt=checkRuntime();
    initializeSNPE(runt);
}

void sendPrediction(std::vector<float> modelOutputVec, PubSocket* traffic_lights_sock) {
    float modelOutput[4];
    for (int i = 0; i < 4; i++){  // convert vector to array
        modelOutput[i] = modelOutputVec[i];
        // std::cout << modelOutput[i] << std::endl;
    }
    // std::cout << std::endl;

    kj::ArrayPtr<const float> modelOutput_vs(&modelOutput[0], 4);

    capnp::MallocMessageBuilder msg;
    cereal::Event::Builder event = msg.initRoot<cereal::Event>();
    event.setLogMonoTime(nanos_since_boot());
    /*
    auto traffic_lights = event.initTrafficModelRaw();
    traffic_lights.setPrediction(modelOutput_vs);

    auto words = capnp::messageToFlatArray(msg);
    auto bytes = words.asBytes();
    traffic_lights_sock->send((char*)bytes.begin(), bytes.size()); */
}

std::vector<float> runModel(std::vector<float> inputVector) {
    std::unique_ptr<zdl::DlSystem::ITensor> inputTensor = loadInputTensor(snpe, inputVector);  // inputVec)
    zdl::DlSystem::ITensor* tensor = executeNetwork(snpe, inputTensor);

    std::vector<float> outputVector;
    for (auto it = tensor->cbegin(); it != tensor->cend(); ++it ){
        float op = *it;
        outputVector.push_back(op);
        // std::cout << op << std::endl;
    }
    // std::cout << "---\n";
    return outputVector;
}

void writeImageVector(std::vector<float> imageVector){
    ofstream outputfile("/data/cropped");
    std::cout << "written!\n";
    std::copy(imageVector.begin(), imageVector.end(), std::ostream_iterator<float>(outputfile, "\n"));
}

bool shouldStop() {
    std::ifstream infile("/data/openpilot/selfdrive/trafficd/stop");
    return infile.good();
}

void sleepFor(double sec) {
    usleep(sec * secToUs);
}

double rateKeeper(double loopTime, double lastLoop) {
    double toSleep;
    if (lastLoop < 0){  // don't sleep if last loop lagged
        lastLoop = std::max(lastLoop, -modelRate);  // this should ensure we don't keep adding negative time to lastLoop if a frame lags pretty badly
                                                    // negative time being time to subtract from sleep time
        // std::cout << "Last frame lagged by " << -lastLoop << " seconds. Sleeping for " << modelRate - (loopTime * msToSec) + lastLoop << " seconds" << std::endl;
        toSleep = modelRate - (loopTime * msToSec) + lastLoop;  // keep time as close as possible to our rate, this reduces the time slept this iter
    } else {
        toSleep = modelRate - (loopTime * msToSec);
    }
    if (toSleep > 0){  // don't sleep for negative time, in case loop takes too long one iteration
        sleepFor(toSleep);
    } else {
        std::cout << "trafficd lagging by " << -(toSleep / msToSec) << " ms." << std::endl;
    }
    return toSleep;
}

void set_do_exit(int sig) {
    std::cout << "received signal: " << sig << std::endl;
    do_exit = 1;
}

uint8_t clamp(int16_t value) {
    return value<0 ? 0 : (value>255 ? 255 : value);
}

static std::vector<float> getFlatVector(const VIPCBuf* buf, const bool returnBGR) {
    // returns RGB if returnBGR is false
    const size_t width = original_shape[1];
    const size_t height = original_shape[0];

    uint8_t *y = (uint8_t*)buf->addr;
    uint8_t *u = y + (width * height);
    uint8_t *v = u + (width / 2) * (height / 2);

    int b, g, r;
    std::vector<float> bgrVec;
    for (int y_cord = top_crop; y_cord < (original_shape[0] - hood_crop); y_cord++) {
        for (int x_cord = horizontal_crop; x_cord < (original_shape[1] - horizontal_crop); x_cord++) {
            int yy = y[(y_cord * width) + x_cord];
            int uu = u[((y_cord / 2) * (width / 2)) + (x_cord / 2)];
            int vv = v[((y_cord / 2) * (width / 2)) + (x_cord / 2)];

            r = 1.164 * (yy - 16) + 1.596 * (vv - 128);
            g = 1.164 * (yy - 16) - 0.813 * (vv - 128) - 0.391 * (uu - 128);
            b = 1.164 * (yy - 16) + 2.018 * (uu - 128);

            if (returnBGR){
                bgrVec.push_back(clamp(b) / 255.0);
                bgrVec.push_back(clamp(g) / 255.0);
                bgrVec.push_back(clamp(r) / 255.0);
            } else {
                bgrVec.push_back(clamp(r) / 255.0);
                bgrVec.push_back(clamp(g) / 255.0);
                bgrVec.push_back(clamp(b) / 255.0);
            }
        }
    }
    return bgrVec;
}


int main(){
    Context* context = Context::create();
    signal(SIGINT, (sighandler_t)set_do_exit);
    signal(SIGTERM, (sighandler_t)set_do_exit);

    initModel(); // init stuff

    VisionStream stream;

    Context* c = Context::create();
    PubSocket* traffic_lights_sock = PubSocket::create(c, "trafficModelRaw");
    assert(traffic_lights_sock != NULL);
    while (!do_exit){  // keep traffic running in case we can't get a frame (mimicking modeld)
        VisionStreamBufs buf_info;
        int err = visionstream_init(&stream, VISION_STREAM_YUV, true, &buf_info);
        if (err != 0) {
            printf("trafficd: visionstream fail\n");
            usleep(100000);
        }

        double loopStart;
        double loopEnd;
        double lastLoop = 0;
        while (!do_exit){
            loopStart = millis_since_boot();

            VIPCBuf* buf;
            VIPCBufExtra extra;

            buf = visionstream_get(&stream, &extra);
            if (buf == NULL) {
                printf("trafficd: visionstream get failed\n");
                break;
            }
            cout << buf << endl;
            std::vector<float> imageVector = getFlatVector(buf, true);
            // Build capnp message
            capnp::MallocMessageBuilder message;

            cereal::Event::Builder event_builder = message.initRoot<cereal::Event>();
            event_builder.setLogMonoTime(0); // TODO

            cereal::FrameData::Builder frame_builder = event_builder.initFrame();
            frame_builder.setImage(kj::arrayPtr(frame_buffer, frame_size));

    
            kj::VectorOutputStream stream;
            capnp::writeMessage(stream, message);
            kj::ArrayPtr<unsigned char> stream_array = stream.getArray();
            sock->send(reinterpret_cast<char*>(stream_array.begin()), stream_array.size());

            
        }
    }
    std::cout << "trafficd is dead" << std::endl;
    visionstream_destroy(&stream);
    return 0;
}