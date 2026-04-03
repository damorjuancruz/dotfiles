#!/usr/bin/env bash

while getopts Y:n:f: opt; do
  case $opt in
  Y) test $OPTARG = sign || break ;;
  f) ssh-add -T "${OPTARG%.pub}".pub || ssh-add "${OPTARG%.pub}" ;;
  esac
done

exec ssh-keygen "$@"
