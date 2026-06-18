cmake_minimum_required(VERSION 3.16)
project(webrtc_aec CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# The CI builds webrtc-audio-processing v1.x (meson) and exposes it via pkg-config
# as `webrtc-audio-processing-1`. Find it.
find_package(PkgConfig REQUIRED)
pkg_check_modules(WEBRTC REQUIRED IMPORTED_TARGET webrtc-audio-processing-1)

add_library(webrtc_aec SHARED src/webrtc_aec.cpp)
target_link_libraries(webrtc_aec PRIVATE PkgConfig::WEBRTC)
target_include_directories(webrtc_aec PRIVATE ${WEBRTC_INCLUDE_DIRS})

# Keep the output name stable across platforms: webrtc_aec.dll / libwebrtc_aec.so
set_target_properties(webrtc_aec PROPERTIES OUTPUT_NAME "webrtc_aec")

install(TARGETS webrtc_aec
        RUNTIME DESTINATION .
        LIBRARY DESTINATION .)
