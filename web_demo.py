from transformers import AutoModel, AutoTokenizer
import gradio as gr
import mdtex2html

from knowledge_query import search_similar_text

tokenizer = AutoTokenizer.from_pretrained("E:\huggingface\models--THUDM--chatglm-6b-int4\snapshots\9163f7e6d9b2e5b4f66d9be8d0288473a8ccd027", trust_remote_code=True)
model = AutoModel.from_pretrained("E:\huggingface\models--THUDM--chatglm-6b-int4\snapshots\9163f7e6d9b2e5b4f66d9be8d0288473a8ccd027", trust_remote_code=True).half().cuda()
model = model.eval()
is_knowledge = True

"""Override Chatbot.postprocess"""


def postprocess(self, y):
    if y is None:
        return []
    for i, (message, response) in enumerate(y):
        y[i] = (
            None if message is None else mdtex2html.convert((message)),
            None if response is None else mdtex2html.convert(response),
        )
    return y


gr.Chatbot.postprocess = postprocess


def parse_text(text):
    """copy from https://github.com/GaiZhenbiao/ChuanhuChatGPT/"""
    lines = text.split("\n")
    lines = [line for line in lines if line != ""]
    count = 0
    for i, line in enumerate(lines):
        if "```" in line:
            count += 1
            items = line.split('`')
            if count % 2 == 1:
                lines[i] = f'<pre><code class="language-{items[-1]}">'
            else:
                lines[i] = f'<br></code></pre>'
        else:
            if i > 0:
                if count % 2 == 1:
                    line = line.replace("`", "\`")
                    line = line.replace("<", "&lt;")
                    line = line.replace(">", "&gt;")
                    line = line.replace(" ", "&nbsp;")
                    line = line.replace("*", "&ast;")
                    line = line.replace("_", "&lowbar;")
                    line = line.replace("-", "&#45;")
                    line = line.replace(".", "&#46;")
                    line = line.replace("!", "&#33;")
                    line = line.replace("(", "&#40;")
                    line = line.replace(")", "&#41;")
                    line = line.replace("$", "&#36;")
                lines[i] = "<br>"+line
    text = "".join(lines)
    return text


def predict(input, chatbot, max_length, top_p, temperature, history):
    global is_knowledge

    chatbot.append((parse_text(input), ""))
    query = input
    if is_knowledge:
        res = search_similar_text(input)
        prompt_template = f"""基于以下已知信息，简洁和专业的来回答用户的问题。
如果无法从中得到答案，请说 "当前会话仅支持解决一个类型的问题，请清空历史信息重试"，不允许在答案中添加编造成分，答案请使用中文。

已知内容:
{res}

问题:
{input}
"""
        query = prompt_template
        is_knowledge = False
    for response, history in model.stream_chat(tokenizer, query, history, max_length=max_length, top_p=top_p,
                                               temperature=temperature):
        chatbot[-1] = (parse_text(input), parse_text(response))

        yield chatbot, history


def reset_user_input():
    return gr.update(value='')


def reset_state():
    global is_knowledge

    is_knowledge = False
    return [], []


with gr.Blocks() as demo:
    gr.HTML("""<h1 align="center">阿成的专属Chat</h1>""")

    chatbot = gr.Chatbot()
    with gr.Row():
        with gr.Column(scale=4):
            with gr.Column(scale=12):
                user_input = gr.Textbox(show_label=False, placeholder="Input...", lines=10).style(
                    container=False)
            with gr.Column(min_width=32, scale=1):
                submitBtn = gr.Button("Submit", variant="primary")
        with gr.Column(scale=1):
            emptyBtn = gr.Button("Clear History")
            max_length = gr.Slider(0, 4096, value=2048, step=1.0, label="Maximum length", interactive=True)
            top_p = gr.Slider(0, 1, value=0.7, step=0.01, label="Top P", interactive=True)
            temperature = gr.Slider(0, 1, value=0.95, step=0.01, label="Temperature", interactive=True)

    history = gr.State([])

    submitBtn.click(predict, [user_input, chatbot, max_length, top_p, temperature, history], [chatbot, history],
                    show_progress=True)
    submitBtn.click(reset_user_input, [], [user_input])

    emptyBtn.click(reset_state, outputs=[chatbot, history], show_progress=True)

demo.queue().launch(share=False, inbrowser=True)
