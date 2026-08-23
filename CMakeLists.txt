cmake_minimum_required(VERSION 3.16)

set(_hlolli_wg_violin_top_level OFF)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  project(hlolli_wg_violin VERSION 1.0.0 LANGUAGES C)
  set(_hlolli_wg_violin_top_level ON)
endif()

option(HLOLLI_WG_VIOLIN_STRICT_WARNINGS
       "Enable strict compiler warnings for violin targets" ON)
option(HLOLLI_WG_VIOLIN_WARNINGS_AS_ERRORS
       "Treat violin compiler warnings as errors" OFF)

function(_hlolli_configure_c_target target)
  set_target_properties("${target}" PROPERTIES
    C_STANDARD 11
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
    C_VISIBILITY_PRESET hidden)
  if(HLOLLI_WG_VIOLIN_STRICT_WARNINGS)
    if(MSVC)
      target_compile_options("${target}" PRIVATE /W4)
      if(HLOLLI_WG_VIOLIN_WARNINGS_AS_ERRORS)
        target_compile_options("${target}" PRIVATE /WX)
      endif()
    elseif(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
      target_compile_options("${target}" PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Wconversion
        -Wformat=2
        -Wshadow
        -Wstrict-prototypes)
      if(HLOLLI_WG_VIOLIN_WARNINGS_AS_ERRORS)
        target_compile_options("${target}" PRIVATE -Werror)
      endif()
    endif()
  endif()
endfunction()

set(HLOLLI_WG_VIOLIN_SOURCE
    "${CMAKE_CURRENT_LIST_DIR}/src/hlolli_wg_violin.c")

# A Csound source-tree build already knows its public headers, output folder,
# plugin suffix, and install folder. Use its helper when this project enters
# through add_subdirectory().
if(COMMAND make_plugin AND DEFINED libcsound_public_include_dirs)
  message(STATUS "hlolli_wg_violin: using Csound's make_plugin() helper")
  make_plugin(hlolli_wg_violin "${HLOLLI_WG_VIOLIN_SOURCE}")
  _hlolli_configure_c_target(hlolli_wg_violin)
  target_compile_definitions(hlolli_wg_violin PRIVATE BUILD_PLUGINS)
  set_target_properties(hlolli_wg_violin PROPERTIES
    EXPORT_NAME wg_violin)
  if(TARGET sync_build_include_headers)
    add_dependencies(hlolli_wg_violin sync_build_include_headers)
  endif()
  add_library(hlolli::wg_violin ALIAS hlolli_wg_violin)
  return()
endif()

set(HLOLLI_CSOUND_INCLUDE_DIR "" CACHE PATH
    "Installed include directory containing all public and version headers")

set(_hlolli_default_csound_build
    "${CMAKE_CURRENT_LIST_DIR}/../csound/build")
if(NOT EXISTS "${_hlolli_default_csound_build}/include/version.h")
  set(_hlolli_default_csound_build "")
endif()
set(HLOLLI_CSOUND_BUILD_DIR "${_hlolli_default_csound_build}" CACHE PATH
    "Csound build tree containing generated version headers")

set(_hlolli_default_csound_source
    "${CMAKE_CURRENT_LIST_DIR}/../csound")
if(NOT EXISTS "${_hlolli_default_csound_source}/include/csdl.h")
  set(_hlolli_default_csound_source "")
endif()
set(HLOLLI_CSOUND_SOURCE_DIR "${_hlolli_default_csound_source}" CACHE PATH
    "Csound source tree, used when public and generated headers are split")

set(HLOLLI_WG_VIOLIN_CUSTOM_CMAKE
    "${CMAKE_CURRENT_LIST_DIR}/Custom.cmake" CACHE FILEPATH
    "Optional local CMake settings file")
if(EXISTS "${HLOLLI_WG_VIOLIN_CUSTOM_CMAKE}")
  message(STATUS
      "hlolli_wg_violin: including ${HLOLLI_WG_VIOLIN_CUSTOM_CMAKE}")
  include("${HLOLLI_WG_VIOLIN_CUSTOM_CMAKE}")
endif()

if(NOT HLOLLI_CSOUND_INCLUDE_DIR AND DEFINED CSOUND_INCLUDE_DIR
    AND NOT "${CSOUND_INCLUDE_DIR}" STREQUAL "")
  set(HLOLLI_CSOUND_INCLUDE_DIR "${CSOUND_INCLUDE_DIR}")
endif()

set(_hlolli_csound_split_include_dirs "")
if(NOT HLOLLI_CSOUND_INCLUDE_DIR AND HLOLLI_CSOUND_BUILD_DIR)
  find_path(_hlolli_csound_build_include
    NAMES csdl.h
    HINTS "${HLOLLI_CSOUND_BUILD_DIR}/include"
    NO_DEFAULT_PATH)
  if(_hlolli_csound_build_include)
    set(HLOLLI_CSOUND_INCLUDE_DIR "${_hlolli_csound_build_include}")
  elseif(HLOLLI_CSOUND_SOURCE_DIR
      AND EXISTS "${HLOLLI_CSOUND_SOURCE_DIR}/include/csdl.h"
      AND EXISTS "${HLOLLI_CSOUND_BUILD_DIR}/include/version.h"
      AND EXISTS "${HLOLLI_CSOUND_BUILD_DIR}/include/float-version.h")
    list(APPEND _hlolli_csound_split_include_dirs
      "${HLOLLI_CSOUND_BUILD_DIR}/include"
      "${HLOLLI_CSOUND_SOURCE_DIR}/include")
  endif()
endif()

function(_hlolli_find_csound_header_target result)
  foreach(candidate IN ITEMS
      Csound::CsoundLib64 Csound::CsoundLib Csound::Csound
      CsoundLib64 CsoundLib)
    if(TARGET "${candidate}")
      get_target_property(candidate_includes "${candidate}"
                          INTERFACE_INCLUDE_DIRECTORIES)
      if(candidate_includes
          AND NOT candidate_includes MATCHES "-NOTFOUND$")
        set("${result}" "${candidate}" PARENT_SCOPE)
        return()
      endif()
    endif()
  endforeach()
  set("${result}" "" PARENT_SCOPE)
endfunction()

set(_hlolli_csound_header_target "")
if(NOT HLOLLI_CSOUND_INCLUDE_DIR
    AND NOT _hlolli_csound_split_include_dirs)
  _hlolli_find_csound_header_target(_hlolli_csound_header_target)
endif()

if(NOT HLOLLI_CSOUND_INCLUDE_DIR
    AND NOT _hlolli_csound_split_include_dirs
    AND NOT _hlolli_csound_header_target)
  find_package(Csound 7 CONFIG QUIET)
  _hlolli_find_csound_header_target(_hlolli_csound_header_target)
endif()

if(NOT HLOLLI_CSOUND_INCLUDE_DIR
    AND NOT _hlolli_csound_split_include_dirs
    AND NOT _hlolli_csound_header_target)
  find_path(HLOLLI_CSOUND_INCLUDE_DIR
    NAMES csdl.h
    HINTS
      "$ENV{CSOUND_INCLUDE_DIR}"
      "$ENV{CSOUND_HOME}/include"
      "$ENV{CSOUND_HOME}/Headers"
      "$ENV{HOME}/Library/Frameworks/CsoundLib64.framework/Headers"
      "/Library/Frameworks/CsoundLib64.framework/Headers"
      "/Applications/Csound/CsoundLib64.framework/Headers"
    PATH_SUFFIXES csound Headers)
endif()

set(_hlolli_csound_version_header "")
if(HLOLLI_CSOUND_INCLUDE_DIR)
  foreach(required_header IN ITEMS csdl.h version.h float-version.h)
    if(NOT EXISTS "${HLOLLI_CSOUND_INCLUDE_DIR}/${required_header}")
      message(FATAL_ERROR
        "HLOLLI_CSOUND_INCLUDE_DIR=${HLOLLI_CSOUND_INCLUDE_DIR} lacks "
        "${required_header}. For a source checkout, set HLOLLI_CSOUND_BUILD_DIR "
        "and HLOLLI_CSOUND_SOURCE_DIR instead.")
    endif()
  endforeach()
  set(_hlolli_csound_version_header
      "${HLOLLI_CSOUND_INCLUDE_DIR}/version.h")
elseif(_hlolli_csound_split_include_dirs)
  set(_hlolli_csound_version_header
      "${HLOLLI_CSOUND_BUILD_DIR}/include/version.h")
elseif(NOT _hlolli_csound_header_target)
  message(FATAL_ERROR
    "Could not find Csound headers. Pass "
    "-DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build and, for an "
    "out-of-tree build, -DHLOLLI_CSOUND_SOURCE_DIR=/path/to/csound; or pass "
    "-DHLOLLI_CSOUND_INCLUDE_DIR=/path/containing/all/headers.")
endif()

if(_hlolli_csound_version_header)
  file(STRINGS "${_hlolli_csound_version_header}"
       _hlolli_required_csound_major_line
       REGEX "^#define[ \t]+CS_VERSION")
  string(REGEX MATCH "[0-9]+" _hlolli_required_csound_major
         "${_hlolli_required_csound_major_line}")
  if("${_hlolli_required_csound_major}" STREQUAL ""
      OR _hlolli_required_csound_major LESS 7)
    message(FATAL_ERROR
      "hlolli_wg_violin requires Csound 7 headers; found "
      "${_hlolli_csound_version_header}")
  endif()
endif()

if(APPLE)
  add_library(hlolli_wg_violin SHARED "${HLOLLI_WG_VIOLIN_SOURCE}")
else()
  add_library(hlolli_wg_violin MODULE "${HLOLLI_WG_VIOLIN_SOURCE}")
endif()

_hlolli_configure_c_target(hlolli_wg_violin)
target_compile_definitions(hlolli_wg_violin PRIVATE BUILD_PLUGINS)
if(HLOLLI_CSOUND_INCLUDE_DIR)
  target_include_directories(hlolli_wg_violin SYSTEM PRIVATE
                             "${HLOLLI_CSOUND_INCLUDE_DIR}")
elseif(_hlolli_csound_split_include_dirs)
  target_include_directories(hlolli_wg_violin SYSTEM PRIVATE
                             ${_hlolli_csound_split_include_dirs})
else()
  target_include_directories(hlolli_wg_violin SYSTEM PRIVATE
    "$<TARGET_PROPERTY:${_hlolli_csound_header_target},INTERFACE_INCLUDE_DIRECTORIES>")
endif()

if(UNIX AND NOT APPLE)
  target_link_libraries(hlolli_wg_violin PRIVATE m)
endif()

set_target_properties(hlolli_wg_violin PROPERTIES
  EXPORT_NAME wg_violin)

if(TARGET sync_build_include_headers)
  add_dependencies(hlolli_wg_violin sync_build_include_headers)
endif()

add_library(hlolli::wg_violin ALIAS hlolli_wg_violin)

find_package(Python3 3.8 COMPONENTS Interpreter QUIET)
set(_hlolli_default_workbench
    "${CMAKE_CURRENT_LIST_DIR}/../csound-wasm-plugin-compiler")
if(NOT EXISTS "${_hlolli_default_workbench}/package.json")
  set(_hlolli_default_workbench "")
endif()
set(HLOLLI_WG_VIOLIN_WORKBENCH_DIR "${_hlolli_default_workbench}" CACHE PATH
    "Csound browser opcode workbench checkout")
find_program(HLOLLI_BUN_EXECUTABLE NAMES bun)
if(Python3_Interpreter_FOUND)
  set(_hlolli_wasm_source
      "${CMAKE_CURRENT_BINARY_DIR}/wasm/hlolli_wg_violin.c")
  add_custom_command(
    OUTPUT "${_hlolli_wasm_source}"
    COMMAND "${Python3_EXECUTABLE}" -B
            "${CMAKE_CURRENT_LIST_DIR}/tools/prepare_wasm_source.py"
            --source "${HLOLLI_WG_VIOLIN_SOURCE}"
            --output "${_hlolli_wasm_source}"
    DEPENDS
      "${HLOLLI_WG_VIOLIN_SOURCE}"
      "${CMAKE_CURRENT_LIST_DIR}/tools/prepare_wasm_source.py"
    COMMENT "Preparing bounded browser compiler source"
    VERBATIM)
  add_custom_target(hlolli_wg_violin_prepare_wasm_source
    DEPENDS "${_hlolli_wasm_source}")

  if(HLOLLI_BUN_EXECUTABLE
      AND EXISTS "${HLOLLI_WG_VIOLIN_WORKBENCH_DIR}/package.json"
      AND EXISTS
          "${HLOLLI_WG_VIOLIN_WORKBENCH_DIR}/node_modules/@csound/browser/dist/csound.js")
    add_custom_target(hlolli_wg_violin_check_wasm
      COMMAND "${HLOLLI_BUN_EXECUTABLE}"
              "${CMAKE_CURRENT_LIST_DIR}/tools/run_wasm_workbench_test.ts"
              --compiler-root "${HLOLLI_WG_VIOLIN_WORKBENCH_DIR}"
              --source "${_hlolli_wasm_source}"
              --csd "${CMAKE_CURRENT_LIST_DIR}/examples/wasm_smoke.csd"
              --output "${CMAKE_CURRENT_BINARY_DIR}/wasm/facts.json"
      DEPENDS
        hlolli_wg_violin_prepare_wasm_source
        "${CMAKE_CURRENT_LIST_DIR}/examples/wasm_smoke.csd"
        "${CMAKE_CURRENT_LIST_DIR}/tools/run_wasm_workbench_test.ts"
      WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
      USES_TERMINAL
      COMMENT "Compiling and playing the violin in the browser workbench"
      VERBATIM)
  endif()

  add_custom_target(hlolli_wg_violin_generate_profiles
    COMMAND "${Python3_EXECUTABLE}" -B
            "${CMAKE_CURRENT_LIST_DIR}/tools/generate_profiles.py"
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    COMMENT "Generating embedded violin profile tables"
    VERBATIM)
  add_custom_target(hlolli_wg_violin_check_profiles
    COMMAND "${Python3_EXECUTABLE}" -B
            "${CMAKE_CURRENT_LIST_DIR}/tools/fit_body_modes.py"
            --check
    COMMAND "${Python3_EXECUTABLE}" -B
            "${CMAKE_CURRENT_LIST_DIR}/tools/fit_body_modes.py"
            --self-test
    COMMAND "${Python3_EXECUTABLE}" -B
            "${CMAKE_CURRENT_LIST_DIR}/tools/generate_profiles.py"
            --check
    COMMAND "${Python3_EXECUTABLE}" -B
            "${CMAKE_CURRENT_LIST_DIR}/tools/generate_profiles.py"
            --self-test
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    COMMENT "Checking violin profile data and generated tables"
    VERBATIM)
endif()

include(GNUInstallDirs)
set(_hlolli_plugin_folder "plugins64")
if(_hlolli_csound_version_header
    AND EXISTS "${_hlolli_csound_version_header}")
  file(STRINGS "${_hlolli_csound_version_header}"
       _hlolli_csound_major_line REGEX "^#define[ \t]+CS_VERSION")
  file(STRINGS "${_hlolli_csound_version_header}"
       _hlolli_csound_minor_line REGEX "^#define[ \t]+CS_SUBVER")
  string(REGEX MATCH "[0-9]+" _hlolli_csound_major
         "${_hlolli_csound_major_line}")
  string(REGEX MATCH "[0-9]+" _hlolli_csound_minor
         "${_hlolli_csound_minor_line}")
  if(NOT "${_hlolli_csound_major}" STREQUAL ""
      AND NOT "${_hlolli_csound_minor}" STREQUAL "")
    set(_hlolli_plugin_folder
        "plugins64-${_hlolli_csound_major}.${_hlolli_csound_minor}")
  endif()
endif()

if(DEFINED PLUGIN_INSTALL_DIR AND NOT "${PLUGIN_INSTALL_DIR}" STREQUAL "")
  set(_hlolli_default_install_dir "${PLUGIN_INSTALL_DIR}")
else()
  set(_hlolli_default_install_dir
      "${CMAKE_INSTALL_LIBDIR}/csound/${_hlolli_plugin_folder}")
endif()
set(HLOLLI_CSOUND_PLUGIN_DIR "${_hlolli_default_install_dir}" CACHE STRING
    "Csound runtime plugin install directory")
option(HLOLLI_WG_VIOLIN_INSTALL "Install the Csound runtime module"
       ${_hlolli_wg_violin_top_level})
if(HLOLLI_WG_VIOLIN_INSTALL)
  install(TARGETS hlolli_wg_violin
    LIBRARY DESTINATION "${HLOLLI_CSOUND_PLUGIN_DIR}"
    RUNTIME DESTINATION "${HLOLLI_CSOUND_PLUGIN_DIR}"
    COMPONENT Runtime)
  install(FILES
    "${CMAKE_CURRENT_LIST_DIR}/README.md"
    "${CMAKE_CURRENT_LIST_DIR}/CHANGELOG.md"
    "${CMAKE_CURRENT_LIST_DIR}/LICENSE"
    "${CMAKE_CURRENT_LIST_DIR}/docs/API.md"
    "${CMAKE_CURRENT_LIST_DIR}/docs/BUILD.md"
    "${CMAKE_CURRENT_LIST_DIR}/docs/FITTING.md"
    "${CMAKE_CURRENT_LIST_DIR}/docs/MODEL.md"
    DESTINATION "${CMAKE_INSTALL_DATAROOTDIR}/doc/hlolli_wg_violin"
    COMPONENT Documentation)
  install(FILES
    "${CMAKE_CURRENT_LIST_DIR}/examples/basic.csd"
    "${CMAKE_CURRENT_LIST_DIR}/examples/solo_techniques.csd"
    "${CMAKE_CURRENT_LIST_DIR}/examples/string_section.csd"
    "${CMAKE_CURRENT_LIST_DIR}/examples/wasm_smoke.csd"
    "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd"
    "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_performance.inc"
    "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_stroke.inc"
    "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_score.inc"
    "${CMAKE_CURRENT_LIST_DIR}/examples/violin_distance.inc"
    "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24.csd"
    "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24_score.inc"
    DESTINATION "${CMAKE_INSTALL_DATAROOTDIR}/hlolli_wg_violin/examples"
    COMPONENT Documentation)
endif()

set(CSOUND_EXECUTABLE "" CACHE FILEPATH "Path to the Csound executable")
if(NOT CSOUND_EXECUTABLE)
  find_program(CSOUND_EXECUTABLE NAMES csound csound64)
endif()
set(HLOLLI_ST_NICOLAES_IR
    "$ENV{HOME}/Downloads/IMReverbs/St Nicolaes Church.wav"
    CACHE FILEPATH
    "Stereo 44.1 kHz St Nicolaes Church impulse response")
set(_hlolli_caprice_ftconv_output
    "${CMAKE_CURRENT_BINARY_DIR}/paganini_caprice_24_ftconv.wav")
if(CSOUND_EXECUTABLE)
  if(Python3_Interpreter_FOUND)
    configure_file(
      "${CMAKE_CURRENT_LIST_DIR}/cmake/play_bach_chaconne.cmake.in"
      "${CMAKE_CURRENT_BINARY_DIR}/play_bach_chaconne-worker.cmake.configured"
      @ONLY)
    file(GENERATE
      OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/play_bach_chaconne-$<CONFIG>.cmake"
      INPUT
        "${CMAKE_CURRENT_BINARY_DIR}/play_bach_chaconne-worker.cmake.configured")
    if(CMAKE_CONFIGURATION_TYPES)
      if(CMAKE_DEFAULT_BUILD_TYPE)
        set(_hlolli_chaconne_default_config "${CMAKE_DEFAULT_BUILD_TYPE}")
      else()
        list(GET CMAKE_CONFIGURATION_TYPES 0
             _hlolli_chaconne_default_config)
      endif()
    else()
      set(_hlolli_chaconne_default_config "${CMAKE_BUILD_TYPE}")
    endif()
    configure_file(
      "${CMAKE_CURRENT_LIST_DIR}/cmake/play_bach_chaconne_dispatch.cmake.in"
      "${CMAKE_CURRENT_BINARY_DIR}/play_bach_chaconne.cmake"
      @ONLY)
    add_custom_target(play_bach_chaconne
      COMMAND "${Python3_EXECUTABLE}" -B
              "${CMAKE_CURRENT_LIST_DIR}/tools/play_bach_chaconne.py"
              --csound "${CSOUND_EXECUTABLE}"
              --module "$<TARGET_FILE:hlolli_wg_violin>"
              --csd "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd"
              --score
              "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_score.inc"
              --performance
              "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_performance.inc"
      DEPENDS
        hlolli_wg_violin
        "${CMAKE_CURRENT_LIST_DIR}/tools/play_bach_chaconne.py"
      WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
      USES_TERMINAL
      COMMENT "Playing Bach's Chaconne from Partita No. 2")
  else()
    add_custom_target(play_bach_chaconne
      COMMAND "${CSOUND_EXECUTABLE}"
              "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
              --sample-accurate
              --num-threads=1
              -odac
              "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd"
      DEPENDS hlolli_wg_violin
      WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}/examples"
      USES_TERMINAL
      COMMENT "Playing Bach's Chaconne from Partita No. 2")
  endif()

  add_custom_target(play_paganini_caprice_24
    COMMAND "${CSOUND_EXECUTABLE}"
            "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
            --sample-accurate
            --num-threads=1
            -odac
            "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24.csd"
    DEPENDS hlolli_wg_violin
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    USES_TERMINAL
    COMMENT "Playing Paganini Caprice No. 24")

  add_custom_target(play_solo_techniques
    COMMAND "${CSOUND_EXECUTABLE}"
            "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
            --sample-accurate
            --num-threads=1
            -odac
            "${CMAKE_CURRENT_LIST_DIR}/examples/solo_techniques.csd"
    DEPENDS hlolli_wg_violin
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    USES_TERMINAL
    COMMENT "Playing the solo violin technique tour")

  add_custom_target(play_string_section
    COMMAND "${CSOUND_EXECUTABLE}"
            "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
            --sample-accurate
            --num-threads=1
            -odac
            "${CMAKE_CURRENT_LIST_DIR}/examples/string_section.csd"
    DEPENDS hlolli_wg_violin
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    USES_TERMINAL
    COMMENT "Playing the four-player string section")

  add_custom_target(render_paganini_caprice_24_ftconv
    COMMAND "${CSOUND_EXECUTABLE}"
            "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
            --sample-accurate
            --num-threads=1
            -W
            -s
            --nopeaks
            "--output=${_hlolli_caprice_ftconv_output}"
            "--omacro:ST_NICOLAES_IR=${HLOLLI_ST_NICOLAES_IR}"
            "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24_ftconv.csd"
    DEPENDS
      hlolli_wg_violin
      "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24_ftconv.csd"
      "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24_score.inc"
      "${HLOLLI_ST_NICOLAES_IR}"
    BYPRODUCTS "${_hlolli_caprice_ftconv_output}"
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    USES_TERMINAL
    COMMENT "Rendering Paganini Caprice No. 24 with St Nicolaes Church ftconv"
    VERBATIM)
endif()

option(HLOLLI_WG_VIOLIN_BUILD_TESTS "Add the native Csound tests"
       ${_hlolli_wg_violin_top_level})
if(HLOLLI_WG_VIOLIN_BUILD_TESTS)
  enable_testing()
  if(Python3_Interpreter_FOUND)
    add_test(NAME hlolli_wg_violin.body_mode_fit
      COMMAND "${Python3_EXECUTABLE}" -B
              "${CMAKE_CURRENT_LIST_DIR}/tools/fit_body_modes.py"
              --check)
    set_tests_properties(hlolli_wg_violin.body_mode_fit PROPERTIES
      LABELS "profile;tooling"
      TIMEOUT 30)

    add_test(NAME hlolli_wg_violin.body_mode_fit_self_test
      COMMAND "${Python3_EXECUTABLE}" -B
              "${CMAKE_CURRENT_LIST_DIR}/tools/fit_body_modes.py"
              --self-test)
    set_tests_properties(
      hlolli_wg_violin.body_mode_fit_self_test PROPERTIES
      LABELS "profile;tooling"
      TIMEOUT 30)

    add_test(NAME hlolli_wg_violin.profile_data
      COMMAND "${Python3_EXECUTABLE}" -B
              "${CMAKE_CURRENT_LIST_DIR}/tools/generate_profiles.py"
              --check)
    set_tests_properties(hlolli_wg_violin.profile_data PROPERTIES
      LABELS "profile;tooling"
      TIMEOUT 30)

    add_test(NAME hlolli_wg_violin.profile_generator_self_test
      COMMAND "${Python3_EXECUTABLE}" -B
              "${CMAKE_CURRENT_LIST_DIR}/tools/generate_profiles.py"
              --self-test)
    set_tests_properties(
      hlolli_wg_violin.profile_generator_self_test PROPERTIES
      LABELS "profile;tooling"
      TIMEOUT 30)

    if(APPLE)
      add_library(hlolli_wg_violin_wasm_source_check SHARED
                  "${_hlolli_wasm_source}")
    else()
      add_library(hlolli_wg_violin_wasm_source_check MODULE
                  "${_hlolli_wasm_source}")
    endif()
    _hlolli_configure_c_target(hlolli_wg_violin_wasm_source_check)
    target_compile_definitions(
      hlolli_wg_violin_wasm_source_check PRIVATE BUILD_PLUGINS)
    if(HLOLLI_CSOUND_INCLUDE_DIR)
      target_include_directories(hlolli_wg_violin_wasm_source_check SYSTEM PRIVATE
                                 "${HLOLLI_CSOUND_INCLUDE_DIR}")
    elseif(_hlolli_csound_split_include_dirs)
      target_include_directories(hlolli_wg_violin_wasm_source_check SYSTEM PRIVATE
                                 ${_hlolli_csound_split_include_dirs})
    else()
      target_include_directories(hlolli_wg_violin_wasm_source_check SYSTEM PRIVATE
        "$<TARGET_PROPERTY:${_hlolli_csound_header_target},INTERFACE_INCLUDE_DIRECTORIES>")
    endif()
    if(UNIX AND NOT APPLE)
      target_link_libraries(hlolli_wg_violin_wasm_source_check PRIVATE m)
    endif()
  endif()
  if(CSOUND_EXECUTABLE)
    add_test(NAME hlolli_wg_violin.smoke
      COMMAND "${CSOUND_EXECUTABLE}"
              "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
              -n -d -m128
              "${CMAKE_CURRENT_LIST_DIR}/tests/smoke.csd")
    set_tests_properties(hlolli_wg_violin.smoke PROPERTIES
      LABELS "api"
      TIMEOUT 30)

    add_test(NAME hlolli_wg_violin.caprice24_syntax
      COMMAND "${CSOUND_EXECUTABLE}"
              "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
              --syntax-check-only
              --sample-accurate
              --num-threads=1
              -n -d -m128
              "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24.csd")
    set_tests_properties(hlolli_wg_violin.caprice24_syntax PROPERTIES
      LABELS "api;demo"
      WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}/examples"
      TIMEOUT 30)

    add_test(NAME hlolli_wg_violin.bach_chaconne_syntax
      COMMAND "${CSOUND_EXECUTABLE}"
              "--opcode-lib=$<TARGET_FILE:hlolli_wg_violin>"
              --syntax-check-only
              --sample-accurate
              --num-threads=1
              -n -d -m128
              "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd")
    set_tests_properties(hlolli_wg_violin.bach_chaconne_syntax PROPERTIES
      LABELS "api;demo"
      WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}/examples"
      TIMEOUT 30)

    if(Python3_Interpreter_FOUND)
      add_test(NAME hlolli_wg_violin.bach_chaconne_score
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tools/generate_bach_chaconne_demo.py"
                --check
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_score.inc")
      set_tests_properties(hlolli_wg_violin.bach_chaconne_score PROPERTIES
        LABELS "demo"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.bach_stroke_shape
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_bach_stroke_shape_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --csd
                "${CMAKE_CURRENT_LIST_DIR}/tests/bach_stroke_shape.csd")
      set_tests_properties(hlolli_wg_violin.bach_stroke_shape PROPERTIES
        LABELS "demo;gesture;bow"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.violin_distance
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_violin_distance_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --csd
                "${CMAKE_CURRENT_LIST_DIR}/tests/violin_distance.csd")
      set_tests_properties(hlolli_wg_violin.violin_distance PROPERTIES
        LABELS "demo;distance;room"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.bach_playback
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_bach_playback_test.py"
                --python "${Python3_EXECUTABLE}"
                --player
                "${CMAKE_CURRENT_LIST_DIR}/tools/play_bach_chaconne.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd"
                --score
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_score.inc"
                --performance
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_performance.inc")
      set_tests_properties(hlolli_wg_violin.bach_playback PROPERTIES
        LABELS "demo;gesture;bow;room"
        TIMEOUT 60)

      add_test(NAME hlolli_wg_violin.bach_resonance
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_chaconne_resonance_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd"
                --score
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_score.inc"
                --performance
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_performance.inc")
      set_tests_properties(hlolli_wg_violin.bach_resonance PROPERTIES
        LABELS "demo;body;resonance"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.bach_sustain
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_chaconne_sustain_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd"
                --score
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_score.inc"
                --performance
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_performance.inc")
      set_tests_properties(hlolli_wg_violin.bach_sustain PROPERTIES
        LABELS "demo;bow;sustain"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.bach_contact
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_chaconne_contact_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne.csd"
                --score
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_score.inc"
                --performance
                "${CMAKE_CURRENT_LIST_DIR}/examples/bach_chaconne_performance.inc")
      set_tests_properties(hlolli_wg_violin.bach_contact PROPERTIES
        LABELS "demo;gesture;bow;continuity"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.caprice24_score
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tools/generate_caprice_24_demo.py"
                --check
                "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24_score.inc"
                --analyzer-score
                "${CMAKE_CURRENT_BINARY_DIR}/paganini_caprice_24_score.csv"
                --analyzer-labels
                "${CMAKE_CURRENT_BINARY_DIR}/paganini_caprice_24_labels.csv")
      set_tests_properties(hlolli_wg_violin.caprice24_score PROPERTIES
        LABELS "demo"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.caprice24_analyzer_alias
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tools/generate_caprice_24_demo.py"
                --check
                "${CMAKE_CURRENT_LIST_DIR}/examples/paganini_caprice_24_score.inc"
                --analyzer-score
                "${CMAKE_CURRENT_BINARY_DIR}/paganini_caprice_24_alias.csv"
                --analyzer-labels
                "${CMAKE_CURRENT_BINARY_DIR}/paganini_caprice_24_alias.csv")
      set_tests_properties(
        hlolli_wg_violin.caprice24_analyzer_alias PROPERTIES
        DEPENDS hlolli_wg_violin.caprice24_score
        LABELS "demo;tooling"
        WILL_FAIL TRUE
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.caprice24_analyzer_output_safety
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/test_caprice_analyzer_exports.py")
      set_tests_properties(
        hlolli_wg_violin.caprice24_analyzer_output_safety PROPERTIES
        LABELS "demo;tooling"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.physical_probe_generator
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/test_physical_probe_generator.py")
      set_tests_properties(
        hlolli_wg_violin.physical_probe_generator PROPERTIES
        LABELS "demo;tooling;physical"
        TIMEOUT 30)

      add_test(NAME hlolli_wg_violin.fit_adapter
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/test_violin_fit_adapter.py")
      set_tests_properties(
        hlolli_wg_violin.fit_adapter PROPERTIES
        LABELS "tooling;fit"
        TIMEOUT 30)

      if(APPLE)
        add_library(hlolli_wg_violin_test SHARED
                    "${HLOLLI_WG_VIOLIN_SOURCE}")
      else()
        add_library(hlolli_wg_violin_test MODULE
                    "${HLOLLI_WG_VIOLIN_SOURCE}")
      endif()
      _hlolli_configure_c_target(hlolli_wg_violin_test)
      target_compile_definitions(hlolli_wg_violin_test PRIVATE
        BUILD_PLUGINS
        HLOLLI_WG_VIOLIN_TEST_API=1)
      if(HLOLLI_CSOUND_INCLUDE_DIR)
        target_include_directories(hlolli_wg_violin_test SYSTEM PRIVATE
                                   "${HLOLLI_CSOUND_INCLUDE_DIR}")
      elseif(_hlolli_csound_split_include_dirs)
        target_include_directories(hlolli_wg_violin_test SYSTEM PRIVATE
                                   ${_hlolli_csound_split_include_dirs})
      else()
        target_include_directories(hlolli_wg_violin_test SYSTEM PRIVATE
          "$<TARGET_PROPERTY:${_hlolli_csound_header_target},INTERFACE_INCLUDE_DIRECTORIES>")
      endif()
      if(UNIX AND NOT APPLE)
        target_link_libraries(hlolli_wg_violin_test PRIVATE m)
      endif()
      if(TARGET sync_build_include_headers)
        add_dependencies(hlolli_wg_violin_test sync_build_include_headers)
      endif()
      add_dependencies(hlolli_wg_violin hlolli_wg_violin_test)

      if(APPLE)
        add_library(hlolli_wg_violin_thermal_neutral_test SHARED
                    "${HLOLLI_WG_VIOLIN_SOURCE}")
      else()
        add_library(hlolli_wg_violin_thermal_neutral_test MODULE
                    "${HLOLLI_WG_VIOLIN_SOURCE}")
      endif()
      _hlolli_configure_c_target(hlolli_wg_violin_thermal_neutral_test)
      target_compile_definitions(
        hlolli_wg_violin_thermal_neutral_test PRIVATE
        BUILD_PLUGINS
        HLOLLI_WG_VIOLIN_TEST_API=1
        WG_VIOLIN_THERMAL_DROP=0.0)
      if(HLOLLI_CSOUND_INCLUDE_DIR)
        target_include_directories(hlolli_wg_violin_thermal_neutral_test
          SYSTEM PRIVATE "${HLOLLI_CSOUND_INCLUDE_DIR}")
      elseif(_hlolli_csound_split_include_dirs)
        target_include_directories(hlolli_wg_violin_thermal_neutral_test
          SYSTEM PRIVATE ${_hlolli_csound_split_include_dirs})
      else()
        target_include_directories(hlolli_wg_violin_thermal_neutral_test
          SYSTEM PRIVATE
          "$<TARGET_PROPERTY:${_hlolli_csound_header_target},INTERFACE_INCLUDE_DIRECTORIES>")
      endif()
      if(UNIX AND NOT APPLE)
        target_link_libraries(hlolli_wg_violin_thermal_neutral_test PRIVATE m)
      endif()
      if(TARGET sync_build_include_headers)
        add_dependencies(
          hlolli_wg_violin_thermal_neutral_test sync_build_include_headers)
      endif()
      add_dependencies(
        hlolli_wg_violin hlolli_wg_violin_thermal_neutral_test)

      add_test(NAME hlolli_wg_violin.ownership
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_ownership_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --ownership-csd
                "${CMAKE_CURRENT_LIST_DIR}/tests/ownership.csd"
                --handoff-csd
                "${CMAKE_CURRENT_LIST_DIR}/tests/handoff.csd")
      set_tests_properties(hlolli_wg_violin.ownership PROPERTIES
        LABELS "ownership"
        RUN_SERIAL TRUE
        TIMEOUT 60)

      add_test(NAME hlolli_wg_violin.string
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_string_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/string.csd")
      set_tests_properties(hlolli_wg_violin.string PROPERTIES
        LABELS "string"
        RUN_SERIAL TRUE
        TIMEOUT 90)

      add_test(NAME hlolli_wg_violin.bow
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_bow_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/bow.csd")
      set_tests_properties(hlolli_wg_violin.bow PROPERTIES
        LABELS "bow;string"
        RUN_SERIAL TRUE
        TIMEOUT 120)

      add_test(NAME hlolli_wg_violin.body
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_body_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/body.csd")
      set_tests_properties(hlolli_wg_violin.body PROPERTIES
        LABELS "body;string"
        RUN_SERIAL TRUE
        TIMEOUT 150)

      add_test(NAME hlolli_wg_violin.legato
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_legato_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/legato.csd")
      set_tests_properties(hlolli_wg_violin.legato PROPERTIES
        LABELS "legato;string"
        RUN_SERIAL TRUE
        TIMEOUT 120)

      add_test(NAME hlolli_wg_violin.exciters
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_exciter_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/exciters.csd")
      set_tests_properties(hlolli_wg_violin.exciters PROPERTIES
        LABELS "exciter;string;body"
        RUN_SERIAL TRUE
        TIMEOUT 150)

      add_test(NAME hlolli_wg_violin.harmonics
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_harmonic_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/harmonics.csd")
      set_tests_properties(hlolli_wg_violin.harmonics PROPERTIES
        LABELS "harmonic;legato;string;body"
        RUN_SERIAL TRUE
        TIMEOUT 180)

      add_test(NAME hlolli_wg_violin.gesture
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_gesture_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/gesture.csd")
      set_tests_properties(hlolli_wg_violin.gesture PROPERTIES
        LABELS "gesture;bow;legato;string;body"
        RUN_SERIAL TRUE
        TIMEOUT 180)

      add_test(NAME hlolli_wg_violin.physics
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_physics_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --thermal-neutral-module
                "$<TARGET_FILE:hlolli_wg_violin_thermal_neutral_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/physics.csd")
      set_tests_properties(hlolli_wg_violin.physics PROPERTIES
        LABELS "physics;bow;string;body;ownership"
        RUN_SERIAL TRUE
        TIMEOUT 240)

      add_test(NAME hlolli_wg_violin.sympathetic
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_sympathetic_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/sympathetic.csd")
      set_tests_properties(hlolli_wg_violin.sympathetic PROPERTIES
        LABELS "sympathetic;strange;physics;string;body;ownership"
        RUN_SERIAL TRUE
        TIMEOUT 300)

      add_test(NAME hlolli_wg_violin.profiles
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_profile_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/profiles.csd")
      set_tests_properties(hlolli_wg_violin.profiles PROPERTIES
        LABELS "profile;body;ownership"
        RUN_SERIAL TRUE
        TIMEOUT 180)

      add_test(NAME hlolli_wg_violin.realism_diagnostic
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_realism_diagnostic_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin_test>"
                --csd
                "${CMAKE_CURRENT_LIST_DIR}/examples/realism_diagnostic.csd")
      set_tests_properties(hlolli_wg_violin.realism_diagnostic PROPERTIES
        LABELS "realism;physics;gesture"
        RUN_SERIAL TRUE
        TIMEOUT 90)

      add_test(NAME hlolli_wg_violin.release_native
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_release_gate.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --prepared-module
                "$<TARGET_FILE:hlolli_wg_violin_wasm_source_check>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/tests/release_gate.csd")
      set_tests_properties(hlolli_wg_violin.release_native PROPERTIES
        LABELS "release;native;worker;performance"
        RUN_SERIAL TRUE
        TIMEOUT 180)

      if(TARGET hlolli_wg_violin_check_wasm)
        add_test(NAME hlolli_wg_violin.release_wasm
          COMMAND "${HLOLLI_BUN_EXECUTABLE}"
                  "${CMAKE_CURRENT_LIST_DIR}/tools/run_wasm_workbench_test.ts"
                  --compiler-root "${HLOLLI_WG_VIOLIN_WORKBENCH_DIR}"
                  --source "${_hlolli_wasm_source}"
                  --csd "${CMAKE_CURRENT_LIST_DIR}/examples/wasm_smoke.csd"
                  --output "${CMAKE_CURRENT_BINARY_DIR}/wasm/facts.json")
        set_tests_properties(hlolli_wg_violin.release_wasm PROPERTIES
          LABELS "release;wasm;browser"
          RUN_SERIAL TRUE
          TIMEOUT 120)
      endif()

      add_test(NAME hlolli_wg_violin.release_demos
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/tests/run_release_demo_test.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --examples "${CMAKE_CURRENT_LIST_DIR}/examples")
      set_tests_properties(hlolli_wg_violin.release_demos PROPERTIES
        LABELS "demo;release"
        RUN_SERIAL TRUE
        TIMEOUT 180)

      add_test(NAME hlolli_wg_violin.release_benchmark_smoke
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/benchmarks/run_release_benchmark.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/benchmarks/release_loads.csd"
                --seconds 0.25
                --repeats 1)
      set_tests_properties(
        hlolli_wg_violin.release_benchmark_smoke PROPERTIES
        LABELS "release;benchmark;performance"
        RUN_SERIAL TRUE
        TIMEOUT 120)

      add_test(NAME hlolli_wg_violin.release_benchmark_comparator
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/benchmarks/run_release_benchmark.py"
                --self-test)
      set_tests_properties(
        hlolli_wg_violin.release_benchmark_comparator PROPERTIES
        LABELS "release;benchmark;performance;tooling"
        TIMEOUT 30)

      add_custom_target(benchmark_bow_contact
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/benchmarks/run_bow_contact_benchmark.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/benchmarks/bow_contact.csd"
        DEPENDS hlolli_wg_violin
        WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
        USES_TERMINAL
        COMMENT "Measuring bowed-string contact CPU cost")

      add_custom_target(benchmark_sympathetic
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/benchmarks/run_sympathetic_benchmark.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/benchmarks/sympathetic.csd"
        DEPENDS hlolli_wg_violin
        WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
        USES_TERMINAL
        COMMENT "Measuring sympathetic-string and kStrange CPU cost")

      add_custom_target(benchmark_release
        COMMAND "${Python3_EXECUTABLE}"
                -B
                "${CMAKE_CURRENT_LIST_DIR}/benchmarks/run_release_benchmark.py"
                --csound "${CSOUND_EXECUTABLE}"
                --module "$<TARGET_FILE:hlolli_wg_violin>"
                --csd "${CMAKE_CURRENT_LIST_DIR}/benchmarks/release_loads.csd"
                --output
                "${CMAKE_CURRENT_BINARY_DIR}/release-loads-benchmark.json"
        DEPENDS hlolli_wg_violin
        WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
        USES_TERMINAL
        COMMENT "Measuring the fixed first-release workloads")
    else()
      message(WARNING
        "Python 3 was not found; ownership, string, bow, body, legato, "
        "exciter, harmonic, gesture, physics, sympathetic, and profile "
        "tests are off.")
    endif()
  else()
    message(WARNING
      "Csound was not found; the plugin will build but its tests are off.")
  endif()
endif()
