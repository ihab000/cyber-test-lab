#!/bin/bash

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
gcloud auth activate-service-account --key-file=/secrets/creds.json
gsutil cp /etc/apt/sources.list gs://${MIRROR_BUCKET}/mirrors/files/${MIRROR_OS}/${MIRROR_VERSION}/
gsutil cp -r /etc/apt/sources.list.d gs://${MIRROR_BUCKET}/mirrors/files/${MIRROR_OS}/${MIRROR_VERSION}/