#!/usr/bin/env python3

import os
from PIL import Image
import ffmpeg
from pathlib import Path
import argparse

class MediaConverter:
    @staticmethod
    def convert_image(input_path: str, output_format: str) -> str:
        """Convert image to specified format."""
        try:
            input_path = Path(input_path)
            output_path = input_path.with_suffix(f'.{output_format}')
            
            with Image.open(input_path) as img:
                # Convert to RGB if necessary (e.g., for WEBP)
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.getchannel('A'))
                    img = background
                
                img.save(str(output_path), quality=95)
            return str(output_path)
        except Exception as e:
            raise Exception(f"Image conversion failed: {str(e)}")

    @staticmethod
    def convert_video(input_path: str, output_format: str) -> str:
        """Convert video to specified format."""
        try:
            input_path = Path(input_path)
            output_path = input_path.with_suffix(f'.{output_format}')
            
            stream = ffmpeg.input(str(input_path))
            stream = ffmpeg.output(stream, str(output_path))
            ffmpeg.run(stream, overwrite_output=True)
            
            return str(output_path)
        except Exception as e:
            raise Exception(f"Video conversion failed: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Convert media files between formats')
    parser.add_argument('input_path', help='Path to input file')
    parser.add_argument('output_format', help='Desired output format (e.g., jpg, mp4)')
    args = parser.parse_args()

    input_path = args.input_path
    output_format = args.output_format.lower()

    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' does not exist")
        return

    # Determine if it's an image or video based on extension
    image_formats = {'.webp', '.jpg', '.jpeg', '.png', '.gif'}
    video_formats = {'.avi', '.wmv', '.mp4', '.mov', '.mkv'}
    
    input_ext = Path(input_path).suffix.lower()
    
    try:
        if input_ext in image_formats:
            output_path = MediaConverter.convert_image(input_path, output_format)
            print(f"Image converted successfully: {output_path}")
        elif input_ext in video_formats:
            output_path = MediaConverter.convert_video(input_path, output_format)
            print(f"Video converted successfully: {output_path}")
        else:
            print(f"Unsupported file format: {input_ext}")
    except Exception as e:
        print(f"Conversion failed: {str(e)}")

if __name__ == '__main__':
    main()
