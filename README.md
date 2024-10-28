# ArXiv Paper Summarizer

这是一个自动搜索和总结 arXiv 论文的工具。用户可以输入时间区间和关键词，系统会自动搜索相关论文并使用 Kimi AI 进行总结。

## 功能特点

- 支持按时间区间和关键词搜索 arXiv 论文
- 自动获取论文标题、摘要和链接
- 使用 Kimi AI 对论文进行智能总结
- 生成包含所有信息的文本报告
- 简洁的 Web 界面

## 使用方法

1. 访问网站首页
2. 输入搜索起始日期和结束日期
3. 输入要搜索的关键词
4. 点击"搜索"按钮
5. 等待系统处理完成后自动下载总结报告

## 部署方法

1. 克隆本仓库到本地
2. 配置环境变量（在 .env 文件中设置 KIMI_API_KEY）
3. 安装依赖：`pip install -r requirements.txt`
4. 运行应用：`python app.py`
5. 访问 `http://localhost:5000` 即可使用

## 技术栈

- 后端：Python Flask
- 前端：HTML, CSS, JavaScript
- API：arXiv API, Kimi API
- 部署：GitHub Pages + Flask

## 注意事项

- 请确保配置了正确的 Kimi API 密钥
- 搜索时间区间建议不要太长，以免处理时间过长
- 生成的报告将以 .txt 格式保存
