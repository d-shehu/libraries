#!/bin/bash

ps aux | grep "[n]g build" | awk '{ print $2 }' | xargs kill