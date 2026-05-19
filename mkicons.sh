#!/bin/bash

function makesize()
{
	local SIZE="$1"
  if [[ "$SIZE" -lt 64 ]]; then
		echo "Exporting 'blenderlauncher_${SIZE}px.png' at WxH ${SIZE}x${SIZE} from 'blenderlauncher_small.svg'..."
		inkscape --export-filename="blenderlauncher_${SIZE}px.png" -w "$SIZE" -h "$SIZE" blenderlauncher_small.svg
  else
		echo "Exporting 'blenderlauncher_${SIZE}px.png' at WxH ${SIZE}x${SIZE} from 'blenderlauncher_large.svg'..."
 		inkscape --export-filename="blenderlauncher_${SIZE}px.png" -w "$SIZE" -h "$SIZE" blenderlauncher_large.svg
	fi
}

makesize 256
makesize 128
makesize 96
makesize 64
makesize 48
makesize 32
