from flask import Flask, render_template, request, send_file, jsonify
import arxiv
from openai import OpenAI
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import time
from functools import wraps
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# 初始化 Moonshot API 客户端
client = OpenAI(
    api_key=os.getenv('MOONSHOT_API_KEY'),  # 改用 MOONSHOT_API_KEY
    base_url="https://api.moonshot.cn/v1",
)

# 添加限流装饰器
def rate_limit(max_per_second):
    min_interval = 1.0 / max_per_second
    lock = threading.Lock()
    last_time = [0.0]  # 使用列表存储，以便在闭包中修改

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                current_time = time.time()
                elapsed = current_time - last_time[0]
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                last_time[0] = time.time()
                return func(*args, **kwargs)
        return wrapper
    return decorator

# 修改 get_paper_summary 函数
@rate_limit(max_per_second=2)  # 限制每秒最多2个请求
def get_paper_summary(text, max_retries=5, initial_retry_delay=10):  # 修改为从10秒开始
    """
    获取论文摘要，失败时使用指数退避重试
    :param text: 要总结的文本
    :param max_retries: 最大重试次数
    :param initial_retry_delay: 初始重试延迟（秒）
    """
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                # 指数退避策略,从10秒开始
                retry_delay = initial_retry_delay * (2 ** (attempt - 1))  # 10s, 20s, 40s, 80s...
                logger.info(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)

            logger.info(f"正在调用 Moonshot API... (尝试 {attempt + 1}/{max_retries})")
            completion = client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=[
                    {"role": "system", "content": "你是一个专业的学术论文分析助手。请用中文三句话简明扼要地总结论文的主要内容，包括：1.研究目的 2.采用方法 3.主要结论"},
                    {"role": "user", "content": f"请用三句话总结以下论文：\n\n{text}"}
                ],
                temperature=0.3,
            )
            summary = completion.choices[0].message.content
            logger.info("Moonshot API 调用成功")
            return summary

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Moonshot API 调用失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
            
            # 对于429错误使用更长的等待时间
            if "429" in error_msg:
                retry_delay = initial_retry_delay * (4 ** (attempt))  # 10s, 40s, 160s...
                logger.info(f"遇到限流，等待 {retry_delay} 秒...")
                time.sleep(retry_delay)
            
            if attempt == max_retries - 1:
                return f"API 调用失败（{error_msg}），请稍后重试"

# 修改 search 函数中的并发处理
def process_paper(paper, start_datetime, end_datetime):
    """处理单个论文的函数"""
    paper_date = paper.published.date()
    if start_datetime.date() <= paper_date <= end_datetime.date():
        logger.info(f"正在处理论文: {paper.title}")
        summary = get_paper_summary(paper.summary)
        return {
            'date': paper_date,
            'title': paper.title,
            'authors': [author.name for author in paper.authors],
            'summary': summary,
            'entry_id': paper.entry_id,
            'pdf_url': paper.pdf_url,
        }
    return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    try:
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        keyword = request.form['keyword']
        
        logger.info(f"开始搜索论文: 关键词={keyword}, 时间范围={start_date}到{end_date}")
        
        # 构建 arXiv 查询
        client = arxiv.Client()
        search = arxiv.Search(
            query=keyword,
            max_results=10,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )

        results = list(client.results(search))
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        
        # 使用线程池处理论文
        with ThreadPoolExecutor(max_workers=3) as executor:
            paper_futures = [
                executor.submit(process_paper, paper, start_datetime, end_datetime)
                for paper in results
            ]
            
            processed_papers = [
                future.result() for future in paper_futures
                if future.result() is not None
            ]

        filename = f"arxiv_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"搜索关键词: {keyword}\n")
            f.write(f"时间范围: {start_date} 至 {end_date}\n")
            f.write("="*50 + "\n\n")
            
            if processed_papers:
                for paper in processed_papers:
                    f.write(f"发布时间：{paper['date']}\n")
                    f.write(f"标题：{paper['title']}\n")
                    f.write(f"作者：{', '.join(paper['authors'])}\n")
                    f.write(f"主要内容：\n{paper['summary']}\n\n")
                    f.write(f"arXiv链接：{paper['entry_id']}\n")
                    f.write(f"PDF链接：{paper['pdf_url']}\n")
                    f.write("\n" + "="*50 + "\n\n")
            else:
                logger.warning("未找到符合条件的论文")
                f.write("未找到符合条件的论文。\n")
                f.write("建议：\n")
                f.write("1. 扩大搜索时间范围\n")
                f.write("2. 尝试使用更通用的关键词\n")
                f.write("3. 检查关键词拼写是否正确\n")
                f.write("4. 尝试以下搜索技巧：\n")
                f.write("   - 使用引号来搜索精确短语，如 \"quantum computing\"\n")
                f.write("   - 使用 AND, OR, NOT 来组合关键词\n")
                f.write("   - 在特定字段中搜索，如 ti:关键词 (标题), au:作者名\n")

        logger.info("处理完成，准备发送文件")
        return send_file(filename, as_attachment=True, mimetype='text/plain')
    
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
