const storyData = {
    meta: {
        title: {
            en: "AI Paper Digest: The Evolution",
            zh: "AI Paper Digest: 进化之路"
        },
        subtitle: {
            en: "Catch AI trends. Read less. Know more.",
            zh: "把握 AI 趋势，少读多懂。"
        },
        footer: {
            en: "A journey of 157 days, 132 commits, and one goal: Better reading.",
            zh: "157天的旅程，132次提交，只为一个目标：更好的阅读体验。"
        }
    },
    stats: {
        title: {
            en: "Development Insights",
            zh: "开发洞察"
        },
        heatmap_title: {
            en: "Commit Activity",
            zh: "提交活跃度"
        },
        time_title: {
            en: "Coding Hours",
            zh: "编码时段"
        },
        metrics: {
            commits: {
                label: { en: "Total Commits", zh: "总提交数" },
                value: 133
            },
            days: {
                label: { en: "Active Days", zh: "活跃天数" },
                value: 34
            },
            hours: {
                label: { en: "Development Span", zh: "开发跨度" },
                value: "157 Days"
            }
        },
        heatmap: {"2025-12-21": 5, "2025-12-20": 3, "2025-12-19": 1, "2025-12-17": 3, "2025-12-16": 2, "2025-12-15": 2, "2025-12-14": 3, "2025-12-13": 3, "2025-12-12": 2, "2025-12-01": 2, "2025-11-30": 12, "2025-11-27": 1, "2025-11-24": 3, "2025-11-10": 2, "2025-11-09": 6, "2025-10-11": 2, "2025-10-10": 7, "2025-09-21": 1, "2025-09-09": 1, "2025-09-08": 7, "2025-08-31": 21, "2025-09-07": 1, "2025-08-30": 13, "2025-08-26": 1, "2025-08-25": 6, "2025-08-24": 6, "2025-08-10": 5, "2025-08-09": 4, "2025-08-08": 1, "2025-08-07": 1, "2025-08-05": 1, "2025-08-04": 2, "2025-07-18": 1, "2025-07-17": 2},
        time_dist: {"morning": 28, "afternoon": 38, "evening": 47, "night": 20},
        time_labels: {
            morning: { en: "Morning (6-12)", zh: "上午 (6-12)" },
            afternoon: { en: "Afternoon (12-18)", zh: "下午 (12-18)" },
            evening: { en: "Evening (18-24)", zh: "晚上 (18-24)" },
            night: { en: "Night (0-6)", zh: "深夜 (0-6)" }
        }
    },
    chapters: [
        {
            date: "July 17, 2025",
            title: {
                en: "The Spark",
                zh: "星星之火"
            },
            description: {
                en: "It started with a personal pain point: too many papers, too little time. A simple Python script was born to download PDFs and use AI to summarize them. It was raw, command-line only, but it worked.",
                zh: "一切始于一个痛点：论文太多，时间太少。一个简单的 Python 脚本诞生了，用于下载 PDF 并利用 AI 生成摘要。虽然简陋，只有命令行，但它能用。"
            },
            tags: ["Idea", "CLI", "Python"],
            icon: "💡"
        },
        {
            date: "August 4, 2025",
            title: {
                en: "From CLI to Web",
                zh: "从命令行到 Web"
            },
            description: {
                en: "Reading Markdown files in a terminal wasn't enough. The project evolved into a Flask web app. Suddenly, abstract text became a visual interface. This was the moment it transformed from a 'tool' to a 'service'.",
                zh: "在终端阅读 Markdown 文件远远不够。项目演变成了 Flask Web 应用。突然间，单调的文本变成了可视化的界面。这是它从“工具”转变为“服务”的时刻。"
            },
            tags: ["Flask", "Web App", "UI"],
            icon: "🖥️"
        },
        {
            date: "August 9, 2025",
            title: {
                en: "Designing for Focus",
                zh: "为专注设计"
            },
            description: {
                en: "Learning often happens late at night. We introduced Dark Mode, acknowledging that deep focus comes when the world is quiet. It wasn't just a color scheme—it was a commitment to the learner's natural rhythm.",
                zh: "学习往往发生在深夜。我们引入了深色模式，承认深度专注往往在世界安静时到来。这不仅仅是一个配色方案——这是对学习者自然节奏的适配。"
            },
            tags: ["Dark Mode", "UX", "Design"],
            icon: "🌙"
        },
        {
            date: "August 9, 2025",
            title: {
                en: "Organizing Knowledge",
                zh: "知识的组织"
            },
            description: {
                en: "As the library grew, we needed better ways to organize. We introduced the Tag System, turning a list of papers into a manageable knowledge base. Papers could now be categorized, filtered, and discovered through semantic connections.",
                zh: "随着图书馆的扩大，我们需要更好的组织方式。我们引入了标签系统，将论文列表变成了一个可管理的知识库。论文现在可以通过语义连接进行分类、过滤和发现。"
            },
            tags: ["Tags", "Organization", "Knowledge Base"],
            icon: "🏷️"
        },
        {
            date: "August 10, 2025",
            title: {
                en: "The Automated Pulse",
                zh: "自动化的脉搏"
            },
            description: {
                en: "To keep up with the flood of information, we introduced the RSS Feed Service. The system began to autonomously 'pulse' every day, fetching the latest papers from Hugging Face and ArXiv without human intervention.",
                zh: "为了跟上信息的洪流，我们引入了 RSS Feed 服务。系统开始每天自动“跳动”，无需人工干预即可从 Hugging Face 和 ArXiv 获取最新的论文。"
            },
            tags: ["RSS", "Automation", "Orchestration"],
            icon: "📡"
        },
        {
            date: "August 24-25, 2025",
            title: {
                en: "Freedom of Choice",
                zh: "选择的自由"
            },
            description: {
                en: "Why rely on just one AI? We unlocked support for local LLMs (Ollama) and OpenAI-compatible APIs. Whether you wanted privacy, low cost, or raw power, the choice became yours.",
                zh: "为什么要依赖单一的 AI？我们解锁了对本地 LLM (Ollama) 和 OpenAI 兼容 API 的支持。无论你想要隐私、低成本还是高性能，选择权都在你手中。"
            },
            tags: ["Ollama", "Multi-LLM", "Local"],
            icon: "🔓"
        },
        {
            date: "August 30, 2025",
            title: {
                en: "Crowdsourcing Interests",
                zh: "众包兴趣"
            },
            description: {
                en: "We opened the gates for user contributions. The 'Paper Submission' system was born, allowing users to bring the papers they want to read into the pipeline.",
                zh: "我们开启了用户贡献的大门。“论文提交”系统诞生了，允许用户将他们想要阅读的论文带入处理流程。"
            },
            tags: ["Submission", "Community", "Discovery"],
            icon: "📥"
        },
        {
            date: "August 31, 2025",
            title: {
                en: "The Architecture Shift",
                zh: "架构重塑"
            },
            description: {
                en: "As complexity grew, the code struggled. In a 48-hour sprint (29 commits!), the monolithic app was dismantled and rebuilt into modular services. It was the growing pain needed for future scale.",
                zh: "随着复杂度增加，代码变得难以维护。在48小时的冲刺（29次提交！）中，单体应用被拆解并重建为模块化服务。这是未来扩展所必需的阵痛。"
            },
            tags: ["Refactoring", "Modular", "Architecture"],
            icon: "🏗️"
        },
        {
            date: "September 8, 2025",
            title: {
                en: "Finding the Needle",
                zh: "大海捞针"
            },
            description: {
                en: "With hundreds of papers accumulated, browsing wasn't enough. We added Search engine and Mobile Navigation. The library was now searchable and accessible from your pocket.",
                zh: "随着数百篇论文的积累，仅靠浏览已不够。我们添加了搜索引擎和移动端导航。现在的图书馆不仅可搜索，还能装进口袋。"
            },
            tags: ["Search", "Mobile", "Accessibility"],
            icon: "🔍"
        },
        {
            date: "October 11, 2025",
            title: {
                en: "Workflow Integration",
                zh: "工作流集成"
            },
            description: {
                en: "Reading isn't just consuming; it's planning. We added 'Todo Lists' and 'Favorites'. The digest became a workspace where you could manage your reading pipeline.",
                zh: "阅读不仅仅是消费，更是规划。我们添加了“待读清单”和“收藏夹”。摘要系统变成了一个工作区，你可以在此管理你的阅读流程。"
            },
            tags: ["Todo", "Favorites", "Workflow"],
            icon: "✅"
        },
        {
            date: "November 24-30, 2025",
            title: {
                en: "Understanding You",
                zh: "理解你的需求"
            },
            description: {
                en: "The system evolved from a library into a guide. By tracking interests and reading patterns, we launched the Recommendation Engine. It finally understood what you cared about and surfaced what mattered.",
                zh: "系统从图书馆演变成了向导。通过追踪兴趣和阅读模式，我们推出了推荐引擎。它终于理解了你所关心的内容，并呈现出真正重要的东西。"
            },
            tags: ["Recommendations", "Personalization", "AI"],
            icon: "🧠"
        },
        {
            date: "December 16, 2025",
            title: {
                en: "Pulse of Interests",
                zh: "兴趣的脉搏"
            },
            description: {
                en: "What attracts attention? The 'Trending' feature was introduced to track hot topics over 7 and 30 days, showing the community's shifting focus.",
                zh: "什么吸引了注意力？引入了“趋势”功能，追踪过去7天和30天的热点话题，展示了社区不断变化的关注点。"
            },
            tags: ["Trending", "Analytics", "Community"],
            icon: "📈"
        },
        {
            date: "December 21, 2025",
            title: {
                en: "The Platform Today",
                zh: "今日平台"
            },
            description: {
                en: "Today, it's a solid platform with tiered Quota Management, Async Processing, and a clean UI. It's a dedicated assistant helping learners and pros stay ahead in the fast-moving AI age.",
                zh: "今天，它是一个拥有分层配额管理、异步处理和整洁 UI 的扎实平台。它是一个帮助学习者和专业人士在快速发展的 AI 时代保持领先的专属助手。"
            },
            tags: ["Current State", "Quota", "Async"],
            icon: "🚀"
        }
    ]
};
