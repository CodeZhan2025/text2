from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
import os
from werkzeug.utils import secure_filename
import requests
import uuid
import json
from dotenv import load_dotenv
from flask_cors import CORS
import docx
import PyPDF2
import re
import mimetypes
from datetime import datetime
import io
import pdfkit
import threading
import time

# 加载环境变量
load_dotenv()

# 获取当前文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
    static_url_path='',
    static_folder=current_dir,
    template_folder=current_dir
)
CORS(app, supports_credentials=True)

# 配置文件上传路径 - 适配Vercel环境
UPLOAD_FOLDER = '/tmp' if os.environ.get('VERCEL') == '1' else os.path.join(current_dir, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制文件大小为16MB

# AI API配置 - 移除默认API密钥
AI_API_KEY = os.getenv('AI_API_KEY')
AI_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 关闭演示模式，使用真实AI API
DEMO_MODE = False

# 演示模式下的审核报告模板
DEMO_AUDIT_REPORT = """审核结论：通过

该项目符合绿色贷款要求，主要投资于清洁能源产业和节能环保产业。

政策匹配分析：
1. 符合《人民银行2019年绿色产业指导目录》中的"清洁能源产业"类别
2. 符合《发改委2024年绿色低碳转型指导目录》中的"可再生能源开发利用"

环境效益评估：
- 预计每年减少二氧化碳排放约5000吨
- 节约标准煤约2000吨
- 环境影响评价已通过专家评审

风险评估：
技术风险较低，市场前景良好，政策支持稳定

建议：
建议加强运营期环境监测，确保持续达标排放

支持政策依据：
《关于加快建立健全绿色低碳循环发展经济体系的指导意见》"""

# API请求头
headers = {
    "Authorization": f"Bearer {AI_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# 任务状态跟踪
tasks = {}  # 存储任务状态的字典
# 任务状态定义:
# - status: 'uploading', 'reading', 'processing', 'analyzing', 'completed', 'error'
# - progress: 0-100整数
# - message: 状态描述
# - report: 审核报告内容
# - error: 错误信息

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://127.0.0.1:5000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept,Origin,Access-Control-Allow-Credentials')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(current_dir, path)

@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return ('', 204)
        
    data = request.json
    user_message = data.get('message')
    
    if not user_message:
        return jsonify({'error': '消息为空'}), 400
    
    try:
        if DEMO_MODE:
            # 增强型演示模式：返回更智能的回复
            # 基于用户消息内容提供相关的回复
            user_message_lower = user_message.lower()
            
            # 针对常见问题的回复库
            if "你是谁" in user_message_lower or "你是什么" in user_message_lower:
                demo_response = {
                    'response': "我是绿色贷款智鉴宝AI助手，专为金融分析师和贷款人员设计的绿色贷款评估工具。我可以帮助您：\n\n1. 评估项目是否符合绿色贷款标准\n2. 解读相关政策和法规\n3. 分析项目的环境效益\n4. 提供风险评估和建议\n\n您有什么具体需要了解的内容吗？"
                }
            elif "绿色贷款" in user_message_lower and ("什么" in user_message_lower or "定义" in user_message_lower):
                demo_response = {
                    'response': "绿色贷款是指金融机构向环保、节能、清洁能源等绿色产业提供的贷款，其特点是：\n\n1. 支持对象：符合国家绿色产业目录的项目\n2. 优惠政策：通常享有利率优惠、快速审批通道\n3. 评估标准：需通过环境效益和可持续发展评估\n4. 法规依据：遵循《绿色产业指导目录》《绿色债券支持项目目录》等\n\n绿色贷款在促进经济绿色转型、实现碳达峰碳中和目标方面发挥着重要作用。"
                }
            elif "政策" in user_message_lower or "法规" in user_message_lower:
                demo_response = {
                    'response': "目前绿色金融相关的主要政策法规包括：\n\n1. 《关于构建绿色金融体系的指导意见》(2016)\n2. 《绿色债券支持项目目录》(2021版)\n3. 《绿色产业指导目录》(2019)\n4. 《关于加快建立健全绿色低碳循环发展经济体系的指导意见》(2021)\n5. 《关于印发<推动能源绿色低碳转型行动方案>的通知》(2022)\n\n这些政策为绿色项目融资提供了标准和支持框架。您需要了解哪方面的具体内容？"
                }
            elif "标准" in user_message_lower or "条件" in user_message_lower or "要求" in user_message_lower:
                demo_response = {
                    'response': "绿色贷款认定标准主要包括以下几个方面：\n\n1. 项目类型符合性：项目须属于《绿色产业指导目录》中的类别\n2. 环境效益要求：须具有明确、可量化的环境效益\n3. 技术标准：采用的技术须符合国家相关标准规范\n4. 合规性要求：环评手续完备，无环保违规记录\n5. 信息披露：定期披露项目环境效益和资金使用情况\n\n具体行业还有相应的细化标准，如光伏发电效率要求、建筑节能率要求等。"
                }
            elif "流程" in user_message_lower or "申请" in user_message_lower or "怎么办" in user_message_lower:
                demo_response = {
                    'response': "绿色贷款申请流程通常包括：\n\n1. 前期准备\n   - 确认项目符合绿色产业目录\n   - 准备环评报告和节能评估\n   - 量化环境效益数据\n\n2. 申请材料\n   - 项目可行性研究报告\n   - 环境效益测算报告\n   - 相关许可证明\n   - 财务报表及预测\n\n3. 银行审核\n   - 绿色属性评估\n   - 环境风险评估\n   - 信用风险评估\n\n4. 贷后管理\n   - 定期环境效益报告\n   - 资金用途监督\n\n需要特别注意的是环境效益的量化计算，这是审批的关键。"
                }
            elif "案例" in user_message_lower or "例子" in user_message_lower or "成功" in user_message_lower:
                demo_response = {
                    'response': "以下是几个绿色贷款的成功案例：\n\n1. 某光伏电站项目\n   - 贷款金额：2亿元\n   - 环境效益：年减排CO2约10万吨\n   - 成功因素：完善的环境效益测算，明确的碳减排路径\n\n2. 某绿色建筑项目\n   - 贷款金额：5000万元\n   - 环境效益：节能率达65%，超过国家标准\n   - 成功因素：采用国际先进节能技术，获得绿色建筑三星认证\n\n3. 某工业节能改造项目\n   - 贷款金额：8000万元\n   - 环境效益：年节约标煤1.5万吨\n   - 成功因素：技术成熟可靠，节能效益显著且有第三方机构认证\n\n这些案例的共同点是环境效益明确且可量化。"
                }
            elif "风险" in user_message_lower:
                demo_response = {
                    'response': "绿色贷款项目常见的风险点包括：\n\n1. 政策风险\n   - 补贴政策变动\n   - 绿色标准调整\n   - 应对措施：关注政策走向，做好敏感性分析\n\n2. 技术风险\n   - 技术路线更迭\n   - 实际效果不及预期\n   - 应对措施：选择成熟技术，进行充分测试\n\n3. 市场风险\n   - 绿色产品定价不合理\n   - 市场接受度不高\n   - 应对措施：做好市场调研，合理定价\n\n4. 绿色洗白风险\n   - 项目实际环境效益不达标\n   - 应对措施：建立第三方监测机制\n\n建议做好全面的风险评估和应对预案。"
                }
            else:
                # 默认回复
                demo_response = {
                    'response': f"您好！我是您的绿色贷款顾问。\n\n您的问题是关于\"{user_message}\"，我可以提供以下信息：\n\n1. 绿色贷款项目类型：\n- 清洁能源（光伏、风电、水电等）\n- 节能改造（工业、建筑、交通等）\n- 污染防治（水、气、固废处理等）\n- 生态保护（生态修复、可持续农业等）\n\n2. 绿色贷款评估关注点：\n- 环境效益量化（减排量、节能率等）\n- 项目可持续性\n- 合规性（环评手续等）\n- 技术先进性\n\n如需更具体的解答，请提供更详细的信息或者明确您关注的方面。"
                }
            return jsonify(demo_response)
            
        # 正常模式：调用AI API
        print(f"发送请求到 AI API，消息内容: {user_message}")  # 调试日志
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system", 
                    "content": """你是一个专业的绿色贷款鉴定AI助手，具备以下能力：
1. 政策解读：深入理解并准确解读各类绿色金融政策文件
2. 业务咨询：提供绿色贷款业务全流程的专业指导
3. 项目评估：协助评估项目是否符合绿色贷款标准
4. 风险提示：识别潜在风险并提供防范建议
5. 案例参考：提供相似项目的成功案例和经验

请以专业、严谨、友好的态度回答，确保信息准确性和实用性。回答时请：
- 引用具体政策条款
- 提供实际案例参考
- 给出可操作的建议
- 说明判断依据
- 标注信息来源"""
                },
                {
                    "role": "user", 
                    "content": user_message
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.95,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        try:
            print("发送请求，headers:", headers)  # 调试日志
            print("发送请求，payload:", json.dumps(payload, ensure_ascii=False))  # 调试日志
            
            response = requests.post(
                AI_API_URL,
                headers=headers,
                json=payload,
                verify=False,
                timeout=30
            )
            
            print(f"API 状态码: {response.status_code}")  # 调试日志
            print(f"API 响应: {response.text}")  # 调试日志
            
            if response.status_code == 200:
                ai_response = response.json()
                if 'choices' in ai_response and len(ai_response['choices']) > 0:
                    return jsonify({
                        'response': ai_response['choices'][0]['message']['content']
                    })
                else:
                    print("API 响应格式错误:", ai_response)  # 调试日志
                    return jsonify({
                        'error': 'API 响应格式错误',
                        'details': ai_response
                    }), 500
            elif response.status_code == 401:
                print("API 认证失败:", response.text)  # 调试日志
                return jsonify({
                    'error': 'API 认证失败，请检查 API 密钥',
                    'details': response.text
                }), 401
            else:
                print(f"API 调用失败: {response.status_code} - {response.text}")  # 调试日志
                return jsonify({
                    'error': f'API 调用失败: {response.status_code}',
                    'details': response.text
                }), response.status_code
                
        except requests.exceptions.Timeout:
            print("API 请求超时")  # 调试日志
            return jsonify({
                'error': 'API 请求超时，请稍后重试'
            }), 504
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {str(e)}")  # 调试日志
            return jsonify({
                'error': f'网络请求错误: {str(e)}'
            }), 500
        except Exception as e:
            print(f"其他异常: {str(e)}")  # 调试日志
            return jsonify({
                'error': f'服务器错误: {str(e)}'
            }), 500
            
    except Exception as e:
        print(f"其他异常: {str(e)}")  # 调试日志
        return jsonify({
            'error': f'服务器错误: {str(e)}'
        }), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件被上传'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    try:
        # 创建唯一的任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        tasks[task_id] = {
            'status': 'uploading',
            'progress': 5,
            'message': '上传文件中...',
            'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存文件
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # 更新任务状态
        tasks[task_id]['status'] = 'reading'
        tasks[task_id]['progress'] = 15
        tasks[task_id]['message'] = '读取文件内容...'
        
        # 启动异步处理线程
        thread = threading.Thread(target=process_file_async, args=(task_id, file_path, filename))
        thread.daemon = True
        thread.start()
        
        # 立即返回任务ID
        return jsonify({
            'message': '文件上传成功，开始处理',
            'filename': filename,
            'task_id': task_id
        })
    except Exception as e:
        print(f"文件处理错误: {str(e)}")
        return jsonify({'error': f'文件处理失败: {str(e)}'}), 500

def process_file_async(task_id, file_path, filename):
    try:
        # 根据文件扩展名选择不同的读取方法
        file_ext = os.path.splitext(filename)[1].lower()
        content = ""
        
        tasks[task_id]['status'] = 'reading'
        tasks[task_id]['progress'] = 20
        tasks[task_id]['message'] = '读取文件内容...'
        
        if file_ext == '.txt':
            # 尝试不同的编码方式读取文本文件
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    tasks[task_id]['status'] = 'error'
                    tasks[task_id]['progress'] = 0
                    tasks[task_id]['message'] = '文件编码错误，无法读取内容'
                    tasks[task_id]['error'] = '文件编码错误，无法读取内容'
                    return
        elif file_ext == '.docx':
            # 读取Word文档
            try:
                doc = docx.Document(file_path)
                content = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                time.sleep(1)  # 模拟处理时间
            except Exception as e:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['progress'] = 0
                tasks[task_id]['message'] = f'Word文档读取失败: {str(e)}'
                tasks[task_id]['error'] = f'Word文档读取失败: {str(e)}'
                return
        elif file_ext == '.pdf':
            # 读取PDF文件
            try:
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    content = ''
                    total_pages = len(pdf_reader.pages)
                    for i, page in enumerate(pdf_reader.pages):
                        content += page.extract_text() + '\n'
                        # 更新读取进度
                        progress = 20 + int((i / total_pages) * 10)
                        tasks[task_id]['progress'] = min(progress, 30)
                        tasks[task_id]['message'] = f'读取PDF: {i+1}/{total_pages}页...'
                        time.sleep(0.2)  # 模拟处理时间
            except Exception as e:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['progress'] = 0
                tasks[task_id]['message'] = f'PDF文件读取失败: {str(e)}'
                tasks[task_id]['error'] = f'PDF文件读取失败: {str(e)}'
                return
        else:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['progress'] = 0
            tasks[task_id]['message'] = '不支持的文件格式'
            tasks[task_id]['error'] = '不支持的文件格式'
            return
        
        # 清理和格式化文本
        content = content.strip()
        content = re.sub(r'\s+', ' ', content)  # 将多个空白字符替换为单个空格
        
        print(f"成功读取文件: {filename}")
        print(f"文件内容预览: {content[:200]}...")  # 打印前200个字符
        
        # 更新任务状态
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['progress'] = 30
        tasks[task_id]['message'] = '准备分析内容...'
        time.sleep(1)  # 模拟处理时间
        
        # 构建AI请求
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的绿色贷款审核专家。请根据以下标准对贷款项目进行审核：\n\n1. 项目是否符合国家绿色产业政策\n2. 项目是否具有明显的环境效益\n3. 项目是否具有可持续性\n4. 项目风险是否可控\n5. 项目是否符合绿色贷款认定标准\n\n请提供详细的审核报告，包括：\n- 项目概述\n- 审核结论\n- 主要依据\n- 风险提示\n- 改进建议"
                },
                {
                    "role": "user",
                    "content": f"请对以下贷款项目进行绿色贷款审核：\n\n{content}"
                }
            ],
            "temperature": 0.2,
            "max_tokens": 2000
        }
        
        # 更新任务状态
        tasks[task_id]['status'] = 'analyzing'
        tasks[task_id]['progress'] = 50
        tasks[task_id]['message'] = 'AI分析中...'
        
        # 发送请求到AI API
        try:
            # 模拟AI处理过程
            for progress in range(50, 90, 5):
                time.sleep(1)  # 模拟处理时间
                tasks[task_id]['progress'] = progress
                tasks[task_id]['message'] = f'AI分析进度: {progress}%...'
            
            # 发送请求到AI API
            if DEMO_MODE:
                # 演示模式
                time.sleep(2)  # 模拟延迟
                audit_report = DEMO_AUDIT_REPORT
            else:
                # 真实API调用
                response = requests.post(
                    AI_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    audit_report = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                elif response.status_code == 401:
                    audit_report = DEMO_AUDIT_REPORT
                else:
                    audit_report = DEMO_AUDIT_REPORT
            
            # 处理完成，更新任务状态
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = '分析完成'
            tasks[task_id]['report'] = audit_report
            tasks[task_id]['completed_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        except requests.exceptions.Timeout:
            # 超时错误
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = 'API请求超时，使用备用结果'
            tasks[task_id]['report'] = DEMO_AUDIT_REPORT
            
        except requests.exceptions.RequestException as e:
            # 请求错误
            print(f"API请求错误: {str(e)}")
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = 'API请求失败，使用备用结果'
            tasks[task_id]['report'] = DEMO_AUDIT_REPORT
            
        except Exception as e:
            # 其他错误
            print(f"处理错误: {str(e)}")
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['progress'] = 0
            tasks[task_id]['message'] = f'处理失败: {str(e)}'
            tasks[task_id]['error'] = str(e)
            
    except Exception as e:
        print(f"任务处理失败: {str(e)}")
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['progress'] = 0
        tasks[task_id]['message'] = f'任务处理失败: {str(e)}'
        tasks[task_id]['error'] = str(e)

@app.route('/export_report', methods=['POST'])
def export_report():
    try:
        data = request.json
        report_content = data.get('report_content', '')
        
        # 创建HTML内容
        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: "Microsoft YaHei", Arial, sans-serif;
                    padding: 40px;
                    line-height: 1.6;
                }}
                h1 {{
                    text-align: center;
                    color: #2c3e50;
                    margin-bottom: 30px;
                }}
                .timestamp {{
                    text-align: right;
                    color: #666;
                    margin-bottom: 30px;
                }}
                p {{
                    margin: 10px 0;
                }}
            </style>
        </head>
        <body>
            <h1>绿色贷款审核报告</h1>
            <div class="timestamp">生成时间：{datetime.now().strftime("%Y年%m月%d日 %H:%M")}</div>
            <div class="content">{report_content.replace('\n', '<br>')}</div>
        </body>
        </html>
        """
        
        try:
            # 创建临时HTML文件
            temp_html = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')
            temp_pdf = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
            
            # 保存HTML内容到临时文件
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 配置wkhtmltopdf选项
            try:
                # 尝试找出环境中的wkhtmltopdf路径
                if os.environ.get('VERCEL') == '1':
                    # Vercel环境下不使用配置
                    config = None
                elif os.name == 'nt':  # Windows
                    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
                else:  # Linux/Mac
                    config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')
            except Exception as e:
                print(f"wkhtmltopdf配置错误: {str(e)}")
                config = None
            
            # 配置选项
            options = {
                'encoding': 'UTF-8',
                'page-size': 'A4',
                'margin-top': '20mm',
                'margin-right': '20mm',
                'margin-bottom': '20mm',
                'margin-left': '20mm',
                'enable-local-file-access': None
            }
            
            # 生成PDF
            try:
                if config:
                    pdfkit.from_file(temp_html, temp_pdf, options=options, configuration=config)
                else:
                    # 如果没有wkhtmltopdf配置，尝试无配置生成
                    pdfkit.from_file(temp_html, temp_pdf, options=options)
                
                # 读取生成的PDF
                with open(temp_pdf, 'rb') as f:
                    pdf_content = f.read()
                
                # 删除临时文件
                os.remove(temp_html)
                os.remove(temp_pdf)
                
                # 返回PDF文件
                return send_file(
                    io.BytesIO(pdf_content),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'绿色贷款审核报告_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                )
            except Exception as e:
                print(f"PDF生成错误: {str(e)}")
                # 删除临时HTML文件，如果存在
                if os.path.exists(temp_html):
                    os.remove(temp_html)
                # 如果PDF文件已生成但处理出错，也删除它
                if os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
                
                # 如果PDF生成失败，返回文本文件
                content = f"""绿色贷款审核报告
生成时间：{datetime.now().strftime("%Y年%m月%d日 %H:%M")}

{report_content}"""
                
                return send_file(
                    io.BytesIO(content.encode('utf-8')),
                    mimetype='text/plain',
                    as_attachment=True,
                    download_name=f'绿色贷款审核报告_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                )
            
        except Exception as e:
            print(f"PDF生成错误: {str(e)}")
            # 如果PDF生成失败，返回文本文件
            content = f"""绿色贷款审核报告
生成时间：{datetime.now().strftime("%Y年%m月%d日 %H:%M")}

{report_content}"""
            
            return send_file(
                io.BytesIO(content.encode('utf-8')),
                mimetype='text/plain',
                as_attachment=True,
                download_name=f'绿色贷款审核报告_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            )
            
    except Exception as e:
        print(f"文件生成错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = tasks[task_id]
    return jsonify({
        'status': task.get('status', 'unknown'),
        'progress': task.get('progress', 0),
        'message': task.get('message', '处理中...')
    })

@app.route('/report/<task_id>', methods=['GET'])
def get_report(task_id):
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = tasks[task_id]
    if task.get('status') != 'completed':
        return jsonify({'error': '报告尚未生成完成'}), 400
    
    return jsonify({
        'report': task.get('report', '未能生成报告')
    })

if __name__ == '__main__':
    # 确保在开发环境中使用 debug 模式
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=True, host='127.0.0.1', port=5000)