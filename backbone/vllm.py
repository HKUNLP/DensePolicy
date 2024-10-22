import os

import numpy as np
import torch
import transformers
import openai
from openai import OpenAI
from transformers import AutoTokenizer

openai_api_key = "EMPTY"

import traceback
import time
import copy
from backbone.num_tokens import num_tokens_from_messages, get_max_context_length
from vllm import LLM, SamplingParams

hf_LM = None
TOKENIZER = None


def call_vllm(
        messages,
        model,
        host=None,
        hist_messages=None,
        stop=None,
        temperature=0.0,
        top_p=1.0,
        max_tokens=None,
        time_limit_query=200,
        use_server=True
):
    if use_server:
        messages = copy.deepcopy(messages)
        hist_messages = copy.deepcopy(hist_messages)
        if hist_messages is not None:
            messages = hist_messages + messages

        # def generate_sample(messages, model) -> str:
        openai_api_base = "http://localhost:{}/v1".format(host)
        client = OpenAI(
            # defaults to os.environ.get("OPENAI_API_KEY")
            api_key=openai_api_key,
            base_url=openai_api_base,
        )
        call_time = 0
        while call_time < 10000:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    n=1,
                    stop=stop,
                    top_p=top_p,
                    stream=False
                )

                resp_msg = response.choices[0].message
                assert resp_msg.role == "assistant"
                messages.append(
                    {"role": "assistant", "content": resp_msg.content}
                )
                return resp_msg.content, messages
                # except Exception as e:
                #     traceback.print_exc()
                #     time.sleep(1)
                #     continue
            except openai.APITimeoutError as e:
                print(e)
                # time.sleep(min(wait, 50+10*np.random.rand()))
                time.sleep(np.random.rand())
                call_time += 1
    else:
        if 'full' in model:
            CKPT_DIR = "TreeDPO/saves"
        else:
            CKPT_DIR = "TreeDPO/models"

        model_file = os.path.join(CKPT_DIR, model)
        global hf_LM
        if hf_LM is None:
            hf_LM = LLM(model=model_file, dtype='float16')

        global TOKENIZER
        if TOKENIZER is None:
            TOKENIZER = AutoTokenizer.from_pretrained(
                model_file)

        messages = copy.deepcopy(messages)
        hist_messages = copy.deepcopy(hist_messages)
        if hist_messages is not None:
            messages = hist_messages + messages
        sampling_params = SamplingParams(max_tokens=max_tokens,
                                         temperature=temperature,
                                         # n=1,
                                         stop=stop,
                                         top_p=top_p)
        # max_tokens = min(max_tokens, get_max_context_length(model, '') - num_tokens_from_messages(messages))
        formatted_messages = TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        # print(formatted_messages)
        response = hf_LM.generate([formatted_messages], sampling_params, use_tqdm=False)
        content = response[0].outputs[0].text
        messages.append(
            {"role": "assistant", "content": content}
        )
        return content, messages

# def call_vllm_local(messages,
#                     model,
#                     hist_messages=None,
#                     stop=None,
#                     temperature=0.0,
#                     top_p=1.0,
#                     max_tokens=None,
#                     time_limit_query=200, ):
#