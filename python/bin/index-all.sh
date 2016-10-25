#!/bin/bash

appurl="https://sandbox-146200.appspot.com/bulkindex"

max=2000000
# should divide evenly into above or else we won't terminate...
fetch=2000

offset=0
until [ "$offset" = "$max" ]; do
	echo "Indexing $fetch from offset $offset"
	curl -i -X POST -F confirm=true -F fetch=$fetch -F offset=$offset "$appurl"

	offset=`expr $offset + $fetch`
	echo "..."
	sleep 10
done


