# embed a single audio file and save to a self-describing format
# we don't need to store information about the file that the example comes from

# Global imports
from pathlib import Path
import numpy as np
# import tqdm
import argparse
import pandas as pd
import soundfile
from math import ceil


from chirp import audio_utils

# we need to house config in this object because
# it's what TaxonomyModelTF expects. Specifically it needs an object that has dot 
# access to values as well as dict-like access for using the spread operator (**config) 
from ml_collections import config_dict

from chirp.inference.models import TaxonomyModelTF


def merge_defaults(config: config_dict):
  """
  gets the config based on user-supplied config and if they are missing then uses defaults
  """

  merged_config = config_dict.create(
    hop_size = 5,
    segment_length = 60,
    max_segments = -1
  )

  if config is None:
    config = config_dict.create()

  for key in config:
    merged_config[key] = config[key]

  return merged_config




def embed_one_file(source: str, output: str, config: config_dict = None):

    config = merge_defaults(config)

    # check audio exists and get the duration
    audio_file = soundfile.SoundFile(source)
    audio_duration = audio_file.frames / audio_file.samplerate
    print(f'analysing {source} samples: {audio_file.frames}, sr: {audio_file.samplerate}, duration {audio_duration} sec')

    model_path = "/models/4"

    # model config contains some values from this function's config plus
    # some values we have fixed.
    model_config = config_dict.create(
        hop_size_s = config.hop_size,
        model_path = model_path,
        sample_rate = 32000,
        window_size_s = 5.0
    )

    output_folder = Path(output)
    output_folder.mkdir(exist_ok=True, parents=True)


    print('\n\nLoading model(s)...')
    #embedding_model = TaxonomyModelTF.from_config(config.embed_fn_config["model_config"])
    embedding_model = TaxonomyModelTF.from_config(model_config)

    # an empty array of the with zero rows to concatenate to
    # 1280 embeddings plus one column for the offset_seconds
    # TODO: I think the shape will be different when we have audio separation channels
    file_embeddings = np.empty((0, 1, 1281))

    total_segments = ceil(audio_duration / config.segment_length)
    num_segments = min(config.max_segments, total_segments) if config.max_segments > 1 else total_segments

    for segment_num in range(num_segments):
      offset_s = config.segment_length * segment_num
      print(f'getting embeddings for offsets {offset_s} to {offset_s + config.segment_length}')

      audio = audio_utils.load_audio_window(
          source, offset_s, 
          model_config.sample_rate, config.segment_length
      )

      if len(audio) > 1:
        embeddings = embedding_model.embed(audio).embeddings

        # the last segment of the file might be smaller than the rest, so we always use its length
        offsets = np.arange(0,embeddings.shape[0]*config.hop_size,config.hop_size).reshape(embeddings.shape[0],1,1) + offset_s

        # if source separation was used, embeddings will have an extra dimention for channel
        # for consistency we will add the extra dimention even if there is only 1 channel

        shape = embeddings.shape
        if len(shape) == 2:
           embeddings = embeddings.reshape(shape[0], 1, shape[1])
        
        segment_embeddings = np.concatenate((offsets, embeddings), axis=2)
        file_embeddings = np.concatenate((file_embeddings, segment_embeddings), axis=0)
      else:
        print('no audio found')
      

    for channel in range(file_embeddings.shape[1]):
        channel_embeddings = file_embeddings[:,channel,:]
        df = pd.DataFrame(channel_embeddings, columns=['offset'] + ['e' + str(i).zfill(3) for i in range(1280)])
        destination_filename = output_folder / Path(f"embeddings_{channel}.csv")


        df.to_csv(destination_filename, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source_file", help="path to the file to analyze")
    parser.add_argument("--output_folder", help="file to embeddings to")
    parser.add_argument("--max_segments", default=-1, type=int, help="only analyse this many segments of the file. Useful for debugging quickly. If ommitted will analyse all")
    parser.add_argument("--segment_length", default=60, type=int,  help="the file is split into segments of this duration in sections to save loading entire files into ram")
    parser.add_argument("--hop_size", default=5, type=float,  help="create an 5 second embedding every this many seconds. Leave as default 5s for no overlap and no gaps.")
    args = parser.parse_args()
    config = config_dict.create(**vars(args))

    embed_one_file(args.source_file, config, args.output_folder)