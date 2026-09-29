cmake_minimum_required(VERSION 3.25)
project(GMCampaignDesignerNext VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

# Les cibles applicatives seront ajoutées par sous-répertoire afin de préserver
# les frontières décrites dans docs/architecture/overview.md.
