#!/bin/sh

jq '.[]._source.layers.btatt.["btatt.value"] | select( . != null )' fullcap.json > fullcap.txt
