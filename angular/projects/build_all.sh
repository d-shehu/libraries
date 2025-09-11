#!/bin/bash

DO_WATCH=$1

watchArg=""
if [ "$DO_WATCH" == "y" ] || [ "$DO_WATCH" == "Y" ]
then
    watchArg="--watch"
    echo "Building and watching Angular libs"
elif [ "$DO_WATCH" != "n" ] && [ "$DO_WATCH" != "N" ]
then
    echo "Unexpected value for 1st argument. Value should be y or n to indicate if watching for code changes."
    exit -1
else
    echo "Building Angular libs only."
fi

LIB_ANG_BUILD_PROJECTS=(
    "app-shell"
)

# Clean up old files
for project in "${LIB_ANG_BUILD_PROJECTS[@]}"
do
    if [ -f "$HOME/project_${project}_build_log.txt" ]
    then
        rm $HOME/project_${project}_build_log.txt
    fi
done

# Run each build in background with optional file watch.
for project in "${LIB_ANG_BUILD_PROJECTS[@]}"
do
    echo "Building $project..."
    nohup ng build $project $watchArg > $HOME/project_${project}_build_log.txt 2>&1 &
    buildProjectPID=$!
done

# Wait for all builds to be ready
didStart="0"
while [ "$didStart" == "0" ]
do
    didStart="1"
    for project in "${LIB_ANG_BUILD_PROJECTS[@]}"
    do
        projectStarted="0"
        if [ -f "$HOME/project_${project}_build_log.txt" ]
        then
            buildMessage="Compilation complete."
            if [ ! -z "$watchArg" ]
            then
                buildMessage="Watching for file changes..."
            fi

            # Match on Compilation message signaling lib project is built
            status=$(more $HOME/project_${project}_build_log.txt | grep "$buildMessage")
            if [ ! -z "status" ]
            then
                echo "Project $project started..."
                projectStarted="1"
            fi
        fi

        # At least one project not build then wait.
        if [ "$projectStarted" == "0" ]
        then
            didStart="0"
        fi
    done
    
    if [ "$didStart" == "0" ]
    then
        echo "Waiting for 1 or more projects ..."
        sleep 1
    fi
done

echo "All projects ready ..."

