from flask import Flask, render_template, request, send_file, jsonify
import arxiv
from openai import OpenAI
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import time

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

def get_paper_summary(text, max_retries=3, retry_delay=2):
    """
    获取论文摘要，失败时自动重试
    :param text: 要总结的文本
    :param max_retries: 最大重试次数
    :param retry_delay: 重试间隔（秒）
    """
    for attempt in range(max_retries):
        try:
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
            logger.error(f"Moonshot API 调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return "API 调用失败，请稍后重试"

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
            query=keyword,  # 直接使用关键词
            max_results=10,  # 增加结果数量
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )

        # 获取结果
        results = list(client.results(search))
        
        filename = f"arxiv_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        papers_found = False
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"搜索关键词: {keyword}\n")
            f.write(f"时间范围: {start_date} 至 {end_date}\n")
            f.write("="*50 + "\n\n")
            
            # 转换日期字符串为 datetime 对象
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            
            for paper in results:
                paper_date = paper.published.date()
                
                # 检查论文日期是否在指定范围内
                if start_datetime.date() <= paper_date <= end_datetime.date():
                    papers_found = True
                    logger.info(f"正在处理论文: {paper.title}")
                    
                    # 获取摘要总结（带重试机制）
                    summary = get_paper_summary(paper.summary)
                    
                    # 写入文件
                    f.write(f"发布时间：{paper_date}\n")
                    f.write(f"标题：{paper.title}\n")
                    f.write(f"作者：{', '.join(author.name for author in paper.authors)}\n")
                    f.write(f"主要内容：\n{summary}\n\n")
                    # f.write(f"arXiv ID: {paper.entry_id.split('/')[-1]}\n")
                    f.write(f"arXiv链接：{paper.entry_id}\n")
                    f.write(f"PDF链接：{paper.pdf_url}\n")
                    # f.write(f"主要分类：{paper.primary_category}\n")
                    # if paper.categories:
                    #     f.write(f"所有分类：{', '.join(paper.categories)}\n")
                    f.write("\n" + "="*50 + "\n\n")
                    
                    # 确保立即写入磁盘
                    f.flush()
                    os.fsync(f.fileno())
        
        if not papers_found:
            logger.warning("未找到符合条件的论文")
            with open(filename, 'a', encoding='utf-8') as f:
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
