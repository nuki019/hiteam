(() => {
  const STORAGE_KEY = "hiteam.v2.prototype";
  const DRAFT_KEY = "hiteam.v2.publishDraft";
  const CURRENT_USER_ID = "u-current";
  const GRADE_OPTIONS = ["大一", "大二", "大三", "大四", "硕士", "博士"];
  const DEFAULT_UI = { role: "applicant", taskStep: "profile", advancedOpen: false, theme: "light" };
  const ROLE_LABELS = { applicant: "申请者", captain: "队长", admin: "系统管理员", creator: "平台创建者" };
  const PROGRAMS = {
    general_competition: {
      id: "general_competition",
      name: "普通竞赛",
      eligibleGrades: null,
      note: "普通竞赛可自定义年级范围。",
    },
    annual_project: {
      id: "annual_project",
      name: "大一年度项目",
      eligibleGrades: ["大一"],
      note: "年度项目仅限大一；项目库是可选来源，人数由项目自行约定。",
    },
    innovation_training: {
      id: "innovation_training",
      name: "大创计划",
      eligibleGrades: ["大二", "大三"],
      note: "大创计划面向大二、大三；项目库是可搜索来源，可关联多个竞赛。",
    },
  };
  const STEP_VIEW = { profile: "profile", discover: "discover", apply: "messages", review: "mine", collaborate: "collaboration" };
  const VIEW_STEP = {
    profile: "profile",
    discover: "discover",
    publish: "review",
    mine: "review",
    messages: "apply",
    collaboration: "collaborate",
    admin: "review",
    files: "collaborate",
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const viewMeta = {
    discover: ["Step 02", "找队伍"],
    publish: ["Captain", "发布招募"],
    profile: ["Step 01", "完善档案"],
    mine: ["Step 04", "队长审核"],
    messages: ["Step 03", "申请进度中心"],
    collaboration: ["Step 05", "匹配后协作"],
    admin: ["Advanced", "管理后台"],
    files: ["Advanced", "文件与备份"],
  };

  let activeDraftId = null;
  let state = loadState();
  let selectedFilterTags = new Set();
  let compactMode = false;
  let pendingLibraryFiles = [];
  let projectSuggestionState = { open: false, options: [], activeIndex: 0 };
  let draftSaveTimer = 0;
  let filterRenderTimer = 0;

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    expireRecruitments();
    setDefaultDeadline();
    bindNavigation();
    bindFilters();
    bindPublish();
    bindProfile();
    bindAwards();
    bindAdmin();
    bindFiles();
    bindGlobalActions();
    showView(STEP_VIEW[currentTaskStep()] || "profile", { step: currentTaskStep(), persist: false });
  }

  function demoState() {
    const now = new Date();
    const plus = (days, hours = 0) => {
      const d = new Date(now);
      d.setDate(d.getDate() + days);
      d.setHours(d.getHours() + hours, 0, 0, 0);
      return d.toISOString();
    };

    const tags = [
      "Python",
      "C++",
      "机器学习",
      "嵌入式",
      "前端",
      "后端",
      "算法竞赛",
      "数学建模",
      "机器人",
      "科研写作",
      "产品设计",
      "数据分析",
      "电控",
      "结构设计",
      "UI设计",
      "英语答辩",
    ].map((name, index) => ({
      id: `tag-${index + 1}`,
      name,
      status: "official",
      createdAt: plus(-12),
    }));

    const competitions = [
      ["中国国际大学生创新大赛", "国家"],
      ["挑战杯", "国家"],
      ["全国大学生电子设计竞赛", "国家"],
      ["RoboMaster 机甲大师", "国家"],
      ["数学建模国赛", "国家"],
      ["ACM-ICPC 区域赛", "国际"],
      ["中国机器人及人工智能大赛", "国家"],
      ["互联网+ 校赛", "校"],
    ].map(([name, level], index) => ({ id: `c-${index + 1}`, name, level }));

    const users = [
      {
        id: CURRENT_USER_ID,
        nickname: "陈一航",
        realName: "陈一航",
        realNameVisibility: "matched",
        avatar: "",
        campus: "一校区",
        college: "计算学部",
        major: "计算机科学与技术",
        grade: "大二",
        contact: "WeChat: hit-team-chen",
        contactVisibility: "matched",
        tags: ["Python", "机器学习", "后端", "科研写作"],
        bio: "做过推荐系统和多模态项目，偏工程落地，能承担后端与模型服务。",
        awards: [
          {
            id: "a-current-1",
            name: "数学建模国赛",
            shortName: "数模国赛",
            level: "national",
            role: "second",
            award: "second",
            bonus: false,
          },
          {
            id: "a-current-2",
            name: "中国国际大学生创新大赛",
            shortName: "国创赛",
            level: "national",
            role: "captain",
            award: "first",
            bonus: true,
          },
        ],
      },
      sampleUser("u-lin", "林思源", "二校区", "航天学院", "飞行器设计", 91.2, 8, [
        "C++",
        "嵌入式",
        "电控",
        "机器人",
      ]),
      sampleUser("u-wang", "王嘉宁", "深圳", "机电工程学院", "自动化", 84.6, 24, [
        "Python",
        "数据分析",
        "数学建模",
        "英语答辩",
      ]),
      sampleUser("u-zhao", "赵予安", "威海", "软件学院", "软件工程", 86.8, 18, [
        "前端",
        "后端",
        "UI设计",
        "产品设计",
      ]),
      sampleUser("u-he", "何清越", "一校区", "材料学院", "材料科学", 89.5, 10, [
        "科研写作",
        "数据分析",
        "英语答辩",
      ]),
      {
        id: "u-admin",
        nickname: "系统管理员",
        realName: "系统管理员",
        realNameVisibility: "private",
        avatar: "",
        campus: "一校区",
        college: "本科生院",
        major: "平台管理",
        grade: "硕士",
        contact: "",
        contactVisibility: "private",
        tags: ["平台治理", "资料维护"],
        bio: "负责项目库、竞赛库和规则资料维护。",
        awards: [],
        systemRole: "admin",
      },
      {
        id: "u-creator",
        nickname: "平台创建者",
        realName: "平台创建者",
        realNameVisibility: "private",
        avatar: "",
        campus: "一校区",
        college: "本科生院",
        major: "平台创建者",
        grade: "硕士",
        contact: "",
        contactVisibility: "private",
        tags: ["平台治理", "权限管理"],
        bio: "拥有平台最高级别的本地原型治理权限。",
        awards: [],
        systemRole: "creator",
      },
    ];

    const recruitments = [
      {
        id: "r-current-1",
        publisherId: CURRENT_USER_ID,
        competition: "中国国际大学生创新大赛",
        competitionSubtitle: "人工智能赛道 / 智能校园问答系统",
        level: "国家",
        campus: "一校区",
        college: "计算学部",
        total: 5,
        current: 3,
        tags: ["机器学习", "后端", "产品设计", "科研写作"],
        grades: ["大二", "大三", "硕士"],
        teacherStatus: "已经找好",
        teacherName: "刘老师",
        summary: "已有 3 人，方向是智能问答系统，已完成需求拆解和初版模型服务。",
        requirement: "希望补一名产品/前端和一名答辩材料同学，能每周稳定投入 8 小时。",
        deadline: plus(12, 3),
        status: "open",
        attachments: [],
        applications: [
          {
            id: "app-1",
            userId: "u-zhao",
            message: "我做过 Vue 和 Figma 原型，也能补产品文档。",
            status: "pending",
            createdAt: plus(-1),
          },
          {
            id: "app-2",
            userId: "u-he",
            message: "可以负责调研、综述和英文答辩材料。",
            status: "pending",
            createdAt: plus(-2),
          },
        ],
        createdAt: plus(-4),
      },
      {
        id: "r-robot",
        publisherId: "u-lin",
        competition: "RoboMaster 机甲大师",
        competitionSubtitle: "视觉识别与电控联调方向",
        level: "国家",
        campus: "二校区",
        college: "航天学院",
        total: 6,
        current: 4,
        tags: ["C++", "嵌入式", "电控", "机器人"],
        grades: ["大一", "大二", "大三"],
        teacherStatus: "尚未找到",
        teacherName: "",
        summary: "电控和机械已有基础，需要补视觉识别与调参方向。",
        requirement: "熟悉 C++ 或 Python，愿意跟进硬件联调，不要求联系指导老师。",
        deadline: plus(9),
        status: "open",
        attachments: [],
        applications: [],
        createdAt: plus(-7),
      },
      {
        id: "r-model",
        publisherId: "u-wang",
        competition: "数学建模国赛",
        competitionSubtitle: "A 题方向预组队 / Python 数据建模",
        level: "国家",
        campus: "深圳",
        college: "机电工程学院",
        total: 3,
        current: 2,
        tags: ["数学建模", "Python", "数据分析", "英语答辩"],
        grades: ["大二", "大三", "大四", "硕士"],
        teacherStatus: "不需要",
        teacherName: "",
        summary: "已有建模与论文同学，需要补一位稳定写代码和可视化的队友。",
        requirement: "熟悉 pandas、可视化、基础优化算法，赛前能完整参加集训。",
        deadline: plus(18),
        status: "open",
        attachments: [],
        applications: [],
        createdAt: plus(-2),
      },
      {
        id: "r-ai",
        publisherId: "u-zhao",
        competition: "中国机器人及人工智能大赛",
        competitionSubtitle: "应用创新赛道 / 校园服务 Agent",
        level: "国家",
        campus: "威海",
        college: "软件学院",
        total: 4,
        current: 3,
        tags: ["机器学习", "前端", "后端", "UI设计"],
        grades: ["大二", "大三", "硕士"],
        teacherStatus: "已经找好",
        teacherName: "张老师",
        summary: "做面向校园服务的轻量 AI Agent，已有原型和数据清洗脚本。",
        requirement: "需要一位前端和一位模型评测同学，重视交付质量。",
        deadline: plus(21),
        status: "open",
        attachments: [],
        applications: [
          {
            id: "app-current-accepted",
            userId: CURRENT_USER_ID,
            message: "我可以负责后端服务、评测脚本和部分答辩材料。",
            status: "accepted",
            createdAt: plus(-3),
            reviewedAt: plus(-1),
          },
        ],
        createdAt: plus(-5),
      },
      {
        id: "r-old",
        publisherId: "u-he",
        competition: "挑战杯",
        competitionSubtitle: "材料多尺度仿真专题",
        level: "国家",
        campus: "一校区",
        college: "材料学院",
        total: 4,
        current: 4,
        tags: ["科研写作", "数据分析", "英语答辩"],
        grades: ["硕士", "博士"],
        teacherStatus: "已经找好",
        teacherName: "周老师",
        summary: "材料多尺度仿真方向，队伍已满。",
        requirement: "当前不再接收新申请。",
        deadline: plus(-2),
        status: "expired",
        attachments: [],
        applications: [],
        createdAt: plus(-20),
      },
    ];

    const projects = [
      {
        id: "p-annual-campus-agent",
        programId: "annual_project",
        title: "智能校园问答助手",
        summary: "面向校园常见事务的问答与资料检索项目，适合从产品、前端和后端分工切入。",
        source: "library",
        libraryYear: "2025级",
        college: "计算学部",
        advisor: "项目库指导教师",
        interdisciplinary: true,
        active: true,
      },
      {
        id: "p-innovation-multimodal",
        programId: "innovation_training",
        title: "校园多模态资料检索",
        summary: "围绕校园资料的文本、图片和表格联合检索，支持后续复用到创新创业类竞赛。",
        source: "library",
        libraryYear: "2025项目库",
        college: "计算学部",
        advisor: "项目库指导教师",
        interdisciplinary: true,
        active: true,
      },
      {
        id: "p-robot-vision",
        programId: "general_competition",
        title: "RoboMaster 视觉识别与电控联调",
        summary: "面向机器人视觉识别与电控联调的工程项目。",
        source: "custom",
        libraryYear: "",
        college: "航天学院",
        advisor: "",
        interdisciplinary: true,
        active: true,
      },
      {
        id: "p-modeling-python",
        programId: "general_competition",
        title: "Python 数据建模与可视化",
        summary: "数学建模赛前预组队，重点补足数据处理、建模和论文表达。",
        source: "custom",
        libraryYear: "",
        college: "机电工程学院",
        advisor: "",
        interdisciplinary: true,
        active: true,
      },
      {
        id: "p-campus-agent",
        programId: "general_competition",
        title: "校园服务 Agent",
        summary: "面向校园服务场景的轻量 Agent 原型与评测项目。",
        source: "custom",
        libraryYear: "",
        college: "软件学院",
        advisor: "张老师",
        interdisciplinary: true,
        active: true,
      },
      {
        id: "p-material-simulation",
        programId: "general_competition",
        title: "材料多尺度仿真专题",
        summary: "材料多尺度仿真方向的研究型项目。",
        source: "custom",
        libraryYear: "",
        college: "材料学院",
        advisor: "周老师",
        interdisciplinary: false,
        active: true,
      },
    ];
    const competitionIdByName = Object.fromEntries(competitions.map((item) => [item.name, item.id]));
    const titleByRecruitment = {
      "r-current-1": "智能校园问答助手",
      "r-robot": "RoboMaster 视觉识别与电控联调",
      "r-model": "Python 数据建模与可视化",
      "r-ai": "校园服务 Agent",
      "r-old": "材料多尺度仿真专题",
    };
    recruitments.forEach((item) => {
      item.programId = item.programId || "general_competition";
      item.projectTitle = titleByRecruitment[item.id] || item.competitionSubtitle || item.competition;
      item.projectId = projects.find((project) => project.title === item.projectTitle)?.id || "";
      item.projectSummary = projects.find((project) => project.id === item.projectId)?.summary || item.summary;
      item.competitionIds = competitionIdByName[item.competition] ? [competitionIdByName[item.competition]] : [];
      item.projectSnapshot = {
        title: item.projectTitle,
        summary: item.projectSummary,
        programId: item.programId,
      };
      delete item.scoreMin;
      delete item.scoreMax;
    });

    return {
      version: "2.0-local-html",
      createdAt: now.toISOString(),
      tags,
      competitions,
      projects,
      projectCompetitionLinks: [
        { projectId: "p-annual-campus-agent", competitionId: "c-1", relation: "可复用至" },
        { projectId: "p-innovation-multimodal", competitionId: "c-2", relation: "可复用至" },
        { projectId: "p-innovation-multimodal", competitionId: "c-1", relation: "可复用至" },
      ],
      users,
      recruitments,
      drafts: [
        {
          id: "draft-annual",
          data: {
            competition: "大一年度项目",
            competitionSubtitle: "智能校园问答助手 / 具体题目待定",
            level: "校",
            campus: "一校区",
            college: "计算学部",
            total: "4",
            current: "1",
            gradeMin: "0",
            gradeMax: "1",
            requiredTags: ["前端", "后端", "产品设计"],
            teacherStatus: "不需要",
            teacherName: "",
            summary: "面向大一年度项目的早期草稿，准备先凑齐产品、前端和后端分工。",
            requirement: "希望能稳定开会，尽快完成题目收敛和原型。",
            deadline: plus(20).slice(0, 16),
            smsCode: "",
            captcha: "",
          },
          updatedAt: plus(-1),
        },
        {
          id: "draft-innovation",
          data: {
            competition: "大学生创新创业训练计划",
            competitionSubtitle: "大创项目 / 校园多模态资料检索",
            level: "校",
            campus: "一校区",
            college: "计算学部",
            total: "5",
            current: "2",
            gradeMin: "1",
            gradeMax: "4",
            requiredTags: ["机器学习", "科研写作", "数据分析"],
            teacherStatus: "尚未找到",
            teacherName: "",
            summary: "围绕大创申报材料准备，已有技术方向和部分数据来源。",
            requirement: "需要能写申报书、做实验记录和数据分析的同学。",
            deadline: plus(28).slice(0, 16),
            smsCode: "",
            captcha: "",
          },
          updatedAt: plus(-2),
        },
      ],
      messages: [
        {
          id: "m-1",
          kind: "notification",
          title: "招募即将截止",
          body: "你发布的中国国际大学生创新大赛招募还有 12 天截止。",
          read: false,
          createdAt: plus(-1),
        },
      ],
      conversations: [
        {
          id: "conv-1",
          title: "系统提示",
          body: "通过申请后，这里会置顶双方联系方式卡片。",
          contact: "",
          read: true,
          createdAt: plus(-1),
        },
      ],
      customTags: [
        {
          id: "ct-1",
          name: "多模态评测",
          requester: "陈一航",
          status: "pending",
          createdAt: plus(-3),
        },
      ],
      reports: [
        {
          id: "rep-1",
          title: "疑似重复招募",
          body: "RoboMaster 招募与旧帖内容相近，建议管理员核对。",
          status: "pending",
          createdAt: plus(-1),
        },
      ],
      files: [],
      platform: {
        creatorId: "u-creator",
        adminIds: ["u-admin"],
        auditLog: [],
      },
    };
  }

  function sampleUser(id, nickname, campus, college, major, gpa, percentile, tags) {
    return {
      id,
      nickname,
      realName: nickname,
      realNameVisibility: id === "u-lin" ? "public" : "matched",
      avatar: "",
      campus,
      college,
      major,
      grade: id === "u-lin" ? "大一" : id === "u-wang" ? "大三" : id === "u-zhao" ? "大二" : "大三",
      contact: `QQ: ${Math.floor(100000000 + Math.random() * 899999999)}`,
      contactVisibility: "matched",
      tags,
      bio: `${college}${major}，关注${tags.slice(0, 2).join("、")}。`,
      awards: [
        {
          id: `${id}-award-1`,
          name: "校级创新项目",
          shortName: "校创项目",
          level: "school",
          role: "captain",
          award: "first",
          bonus: false,
        },
        {
          id: `${id}-award-2`,
          name: "省级学科竞赛",
          shortName: "省赛",
          level: "provincial",
          role: "second",
          award: "second",
          bonus: false,
        },
      ],
    };
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return ensureStateShape(demoState());
      const parsed = JSON.parse(raw);
      if (!parsed || !Array.isArray(parsed.recruitments)) return ensureStateShape(demoState());
      return ensureStateShape(parsed);
    } catch (error) {
      console.warn("Failed to load state", error);
      return ensureStateShape(demoState());
    }
  }

  function ensureStateShape(nextState) {
    nextState.ui = { ...DEFAULT_UI, ...(nextState.ui || {}) };
    if (!ROLE_LABELS[nextState.ui.role]) nextState.ui.role = DEFAULT_UI.role;
    if (!STEP_VIEW[nextState.ui.taskStep]) nextState.ui.taskStep = DEFAULT_UI.taskStep;
    nextState.ui.advancedOpen = Boolean(nextState.ui.advancedOpen);
    if (!['light', 'dark'].includes(nextState.ui.theme)) nextState.ui.theme = DEFAULT_UI.theme;
    nextState.users ||= [];
    nextState.tags ||= [];
    nextState.competitions ||= [];
    nextState.projects ||= demoState().projects || [];
    nextState.projectCompetitionLinks ||= demoState().projectCompetitionLinks || [];
    nextState.platform = {
      creatorId: "u-creator",
      adminIds: [],
      auditLog: [],
      ...(nextState.platform || {}),
    };
    nextState.drafts ||= [];
    nextState.files ||= [];
    nextState.messages ||= [];
    nextState.conversations ||= [];
    nextState.collaboration = nextState.collaboration && typeof nextState.collaboration === "object" ? nextState.collaboration : {};
    nextState.customTags ||= [];
    nextState.reports ||= [];
    nextState.recruitments.forEach((item) => {
      normalizeRecruitment(item, nextState.projects, nextState.competitions);
      item.grades ||= ["大一", "大二", "大三", "大四", "硕士", "博士"];
    });
    nextState.users.forEach((user) => {
      user.tags ||= [];
      user.awards ||= [];
      user.grade ||= "大二";
      user.systemRole ||= null;
      user.awards.forEach((award) => {
        award.shortName ||= shortNameForAward(award.name);
      });
    });
    try {
      const legacyDraft = localStorage.getItem(DRAFT_KEY);
      if (legacyDraft && !nextState.drafts.length) {
        nextState.drafts.push({
          id: uid("draft"),
          data: normalizeDraftData(JSON.parse(legacyDraft)),
          updatedAt: new Date().toISOString(),
        });
      }
    } catch {
      localStorage.removeItem(DRAFT_KEY);
    }
    if (nextState.drafts.length < 2) {
      const templates = demoState().drafts.filter((draft) => !nextState.drafts.some((item) => item.id === draft.id));
      nextState.drafts.push(...templates.slice(0, 2 - nextState.drafts.length));
    }
    activeDraftId = nextState.drafts[0]?.id || null;
    return nextState;
  }

  function defaultCompetitionSubtitle(competition = "") {
    if (competition.includes("创新大赛")) return "人工智能赛道 / 智能校园问答系统";
    if (competition.includes("RoboMaster")) return "视觉识别与电控联调方向";
    if (competition.includes("数学建模")) return "A 题方向预组队 / Python 数据建模";
    if (competition.includes("机器人及人工智能")) return "应用创新赛道 / 校园服务 Agent";
    if (competition.includes("挑战杯")) return "材料多尺度仿真专题";
    return "";
  }

  function programById(id) {
    return PROGRAMS[id] || PROGRAMS.general_competition;
  }

  function projectById(id) {
    return (state.projects || []).find((project) => project.id === id);
  }

  function normalizeRecruitment(item, projects = [], competitions = []) {
    item.programId ||= inferProgramId(item);
    item.projectTitle ||= item.projectSnapshot?.title || item.competitionSubtitle || item.competition || "未命名项目";
    item.projectId ||= projectForTitle(item.projectTitle, projects)?.id || "";
    item.projectSummary ||= item.projectSnapshot?.summary || item.summary || "";
    item.competitionSubtitle ||= defaultCompetitionSubtitle(item.competition);
    item.competitionIds ||= [];
    if (!item.competitionIds.length && item.competition) {
      const found = competitions.find((competition) => competition.name === item.competition);
      if (found) item.competitionIds = [found.id];
    }
    item.projectSnapshot ||= {
      title: item.projectTitle,
      summary: item.projectSummary,
      programId: item.programId,
    };
    return item;
  }

  function inferProgramId(item) {
    const text = `${item.competition || ""} ${item.competitionSubtitle || ""}`;
    if (/年度项目/.test(text)) return "annual_project";
    if (/大创|创新创业训练/.test(text)) return "innovation_training";
    return "general_competition";
  }

  function projectForTitle(title, projects = []) {
    const normalized = normalizeSearchText(title);
    return projects.find((project) => normalizeSearchText(project.title) === normalized);
  }

  function shortNameForAward(name = "") {
    const text = String(name);
    if (text.includes("美国大学生数学建模") || text.includes("美赛")) return "美赛";
    if (text.includes("中国国际大学生创新大赛") || text.includes("创新大赛")) return "国创赛";
    if (text.includes("挑战杯")) return "挑战杯";
    if (text.includes("数学建模")) return "数模国赛";
    if (text.includes("RoboMaster")) return "RM";
    return text.slice(0, 8) || "竞赛";
  }

  function saveState() {
    state.updatedAt = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function expireRecruitments() {
    const now = Date.now();
    state.recruitments.forEach((item) => {
      if (item.status === "open" && new Date(item.deadline).getTime() < now) {
        item.status = "expired";
      }
    });
    saveState();
  }

  function setDefaultDeadline() {
    const input = $('[name="deadline"]');
    if (!input || input.value) return;
    const date = new Date();
    date.setDate(date.getDate() + 14);
    date.setHours(20, 0, 0, 0);
    input.value = date.toISOString().slice(0, 16);
  }

  function currentRole() {
    return state.ui?.role || DEFAULT_UI.role;
  }

  function currentTaskStep() {
    return state.ui?.taskStep || DEFAULT_UI.taskStep;
  }

  function canManageContent(role = currentRole()) {
    return role === "admin" || role === "creator";
  }

  function canManageAdmins(role = currentRole()) {
    return role === "creator";
  }

  function setTaskStep(step, persist = true) {
    if (!STEP_VIEW[step]) return;
    state.ui.taskStep = step;
    if (persist) saveState();
  }

  function setRole(role) {
    if (!ROLE_LABELS[role]) return;
    state.ui.role = role;
    if (role === "captain") {
      state.ui.taskStep = "review";
      saveState();
      showView("mine", { step: "review" });
      return;
    }
    if (role === "admin") {
      state.ui.taskStep = "review";
      state.ui.advancedOpen = true;
      saveState();
      showView("admin", { step: "review" });
      return;
    }
    if (role === "creator") {
      state.ui.taskStep = "review";
      state.ui.advancedOpen = true;
      saveState();
      showView("admin", { step: "review" });
      return;
    }
    state.ui.taskStep = profileReadiness(currentUser()).ready ? "discover" : "profile";
    saveState();
    showView(STEP_VIEW[state.ui.taskStep], { step: state.ui.taskStep });
  }

  function bindNavigation() {
    $$(".nav-item, .mobile-nav").forEach((button) => {
      button.addEventListener("click", () => showView(button.dataset.view, { step: button.dataset.step }));
    });
    $$("[data-view-jump]").forEach((button) => {
      button.addEventListener("click", () => showView(button.dataset.viewJump, { step: button.dataset.stepJump || button.dataset.step }));
    });
    $$("#roleSwitch [data-role]").forEach((button) => {
      button.addEventListener("click", () => setRole(button.dataset.role));
    });
    $("#toggleAdvanced")?.addEventListener("click", () => {
      state.ui.advancedOpen = !state.ui.advancedOpen;
      saveState();
      renderAll();
    });
    $("#toggleTheme")?.addEventListener("click", () => {
      state.ui.theme = state.ui.theme === "dark" ? "light" : "dark";
      saveState();
      renderAll();
    });
  }

  function showView(view, options = {}) {
    const step = options.step || VIEW_STEP[view] || currentTaskStep();
    setTaskStep(step, options.persist !== false);
    if (view === "admin" || view === "files") {
      state.ui.advancedOpen = true;
      if (options.persist !== false) saveState();
    }
    $$(".view").forEach((section) => section.classList.remove("active"));
    $(`#view-${view}`)?.classList.add("active");
    $$(".nav-item, .mobile-nav").forEach((button) => {
      button.classList.toggle("active", button.dataset.step === currentTaskStep());
    });
    const [eyebrow, title] = viewMeta[view] || viewMeta.discover;
    $("#viewEyebrow").textContent = eyebrow;
    $("#viewTitle").textContent = title;
    if (view === "profile") populateProfileForm();
    renderAll();
  }

  function bindFilters() {
    $("#filterForm").addEventListener("input", scheduleFilterRender);
    $("#filterForm").addEventListener("change", () => {
      window.clearTimeout(filterRenderTimer);
      filterRenderTimer = 0;
      renderRecruitments();
    });
    $("#clearFilters").addEventListener("click", () => {
      selectedFilterTags.clear();
      $("#filterForm").reset();
      renderFilterTags();
      renderRecruitments();
    });
    $("#toggleDensity").addEventListener("click", () => {
      compactMode = !compactMode;
      $("#toggleDensity").textContent = compactMode ? "舒展视图" : "紧凑视图";
      renderRecruitments();
    });
  }

  function scheduleFilterRender() {
    window.clearTimeout(filterRenderTimer);
    filterRenderTimer = window.setTimeout(() => {
      filterRenderTimer = 0;
      window.requestAnimationFrame(() => renderRecruitments());
    }, 120);
  }

  function bindPublish() {
    const form = $("#publishForm");
    bindGradeRange(form);
    bindProjectPicker(form);
    bindProgramRules(form);
    form.addEventListener("input", () => scheduleDraftSave(form));
    form.addEventListener("change", () => {
      applyProgramRules(form);
      saveDraftFromForm(form, true);
    });
    $("#savePublishDraft").addEventListener("click", () => saveDraftFromForm(form));
    $("#mobileSaveDraft").addEventListener("click", () => saveDraftFromForm(form));
    $("#mobileSubmitPublish").addEventListener("click", () => form.requestSubmit());
    $("#loadDraft").addEventListener("click", () => loadDraftIntoForm(form));
    $("#newDraft").addEventListener("click", () => createNewDraft(form));
    $("#draftPreviewList").addEventListener("click", (event) => {
      const load = event.target.closest("[data-load-draft]");
      const remove = event.target.closest("[data-delete-draft]");
      if (load) loadDraftIntoForm(form, load.dataset.loadDraft);
      if (remove) deleteDraft(remove.dataset.deleteDraft);
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const draftData = collectPublishDraft(form);
      const errors = validatePublishDraft(draftData);
      renderFieldErrors(errors);
      renderPublishSummary(draftData);
      if (Object.keys(errors).length) {
        toast(Object.values(errors)[0], "error");
        return;
      }
      const total = Number(draftData.total);
      const current = Number(draftData.current);
      const attachments = await readFiles(form.elements.attachments.files, "recruitment");
      const recruitment = {
        id: uid("r"),
        publisherId: CURRENT_USER_ID,
        programId: String(draftData.programId || "general_competition"),
        projectId: String(draftData.projectId || ""),
        projectTitle: String(draftData.projectTitle || "").trim(),
        projectSummary: String(draftData.projectSummary || "").trim(),
        projectSource: draftData.projectSelectionMode === "existing" ? "library" : "custom",
        competitionIds: draftData.competitionIds || [],
        competition: String(draftData.competition).trim(),
        competitionSubtitle: String(draftData.competitionSubtitle || "").trim(),
        level: String(draftData.level),
        campus: String(draftData.campus),
        college: String(draftData.college).trim(),
        total,
        current,
        tags: draftData.requiredTags,
        gradeMin: Number(draftData.gradeMin),
        gradeMax: Number(draftData.gradeMax),
        grades: gradeRangeToValues(draftData.gradeMin, draftData.gradeMax),
        teacherStatus: String(draftData.teacherStatus),
        teacherName: String(draftData.teacherName || "").trim(),
        summary: String(draftData.summary).trim(),
        requirement: String(draftData.requirement).trim(),
        deadline: new Date(String(draftData.deadline)).toISOString(),
        status: "open",
        attachments,
        applications: [],
        createdAt: new Date().toISOString(),
      };
      recruitment.projectSnapshot = {
        title: recruitment.projectTitle,
        summary: recruitment.projectSummary,
        programId: recruitment.programId,
      };
      state.recruitments.unshift(recruitment);
      state.files.push(...attachments);
      addMessage("notification", "招募已发布", `${recruitment.competition} 已进入发现列表。`);
      state.drafts = state.drafts.filter((draft) => draft.id !== activeDraftId);
      activeDraftId = state.drafts[0]?.id || null;
      saveState();
      localStorage.removeItem(DRAFT_KEY);
      form.reset();
      setDefaultDeadline();
      updateGradeRangeLabel(form);
      clearChecklist("publishTagChecklist");
      renderFieldErrors({});
      renderPublishSummary(collectPublishDraft(form));
      renderAll();
      showView("discover");
      toast("招募已发布");
    });
  }

  function bindProgramRules(form) {
    const select = form?.elements.programId;
    if (!select) return;
    select.addEventListener("change", () => applyProgramRules(form));
    applyProgramRules(form);
  }

  function applyProgramRules(form) {
    const program = programById(form?.elements.programId?.value);
    const min = form?.elements.gradeMin;
    const max = form?.elements.gradeMax;
    if (program.eligibleGrades?.length && min && max) {
      const indexes = program.eligibleGrades.map((grade) => GRADE_OPTIONS.indexOf(grade));
      min.value = String(Math.min(...indexes));
      max.value = String(Math.max(...indexes));
      min.disabled = true;
      max.disabled = true;
    } else if (min && max) {
      min.disabled = false;
      max.disabled = false;
    }
    $("#programEligibilityNote").textContent = program.note;
    updateGradeRangeLabel(form);
  }

  function bindProjectPicker(form) {
    const input = $("#projectTitleInput");
    const menu = $("#projectSuggestions");
    if (!input || !menu) return;
    input.addEventListener("input", () => {
      form.elements.projectId.value = "";
      form.elements.projectSelectionMode.value = "new";
      $("#projectSelectionMeta").textContent = input.value.trim() ? "默认可新增项目；按上下键切换到已有项目。" : "输入后可用上下键选择，Enter 确认。";
      renderProjectSuggestions(input.value);
    });
    input.addEventListener("focus", () => renderProjectSuggestions(input.value));
    input.addEventListener("keydown", (event) => {
      if (!projectSuggestionState.open) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        projectSuggestionState.activeIndex = Math.min(projectSuggestionState.activeIndex + 1, projectSuggestionState.options.length - 1);
        renderProjectSuggestions(input.value, true);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        projectSuggestionState.activeIndex = Math.max(projectSuggestionState.activeIndex - 1, 0);
        renderProjectSuggestions(input.value, true);
      } else if (event.key === "Enter") {
        const option = projectSuggestionState.options[projectSuggestionState.activeIndex];
        if (option) {
          event.preventDefault();
          selectProjectOption(option, form);
        }
      } else if (event.key === "Escape") {
        closeProjectSuggestions();
      }
    });
    menu.addEventListener("click", (event) => {
      const option = event.target.closest("[data-project-option]");
      if (!option) return;
      const selected = projectSuggestionState.options[Number(option.dataset.projectOption)];
      if (selected) selectProjectOption(selected, form);
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".project-picker")) closeProjectSuggestions();
    });
  }

  function renderProjectSuggestions(query = "", preserveActive = false) {
    const input = $("#projectTitleInput");
    const menu = $("#projectSuggestions");
    if (!input || !menu) return;
    const normalized = normalizeSearchText(query);
    const projects = (state.projects || []).filter((project) => project.active !== false);
    const matches = projects.filter((project) => {
      if (!normalized) return true;
      return normalizeSearchText(`${project.title} ${project.summary} ${project.college}`).includes(normalized);
    });
    const exact = matches.filter((project) => normalizeSearchText(project.title) === normalized);
    const fuzzy = matches.filter((project) => !exact.includes(project));
    const options = fuzzy.slice(0, 6).map((project) => ({ mode: "existing", project, title: project.title }));
    if (normalized) {
      options.push({ mode: "new", title: String(query).trim() });
      exact.forEach((project) => options.push({ mode: "existing", project, title: project.title }));
    }
    projectSuggestionState.options = options;
    if (!preserveActive) {
      const newIndex = options.findIndex((option) => option.mode === "new");
      projectSuggestionState.activeIndex = newIndex >= 0 ? newIndex : 0;
    }
    projectSuggestionState.open = Boolean(options.length);
    input.setAttribute("aria-expanded", String(projectSuggestionState.open));
    menu.innerHTML = options.length
      ? options
          .map(
            (option, index) => `
              <button class="project-option ${option.mode === "new" ? "new-option" : ""} ${index === projectSuggestionState.activeIndex ? "active" : ""}" type="button" role="option" aria-selected="${index === projectSuggestionState.activeIndex ? "true" : "false"}" data-project-option="${index}">
                <span>${escapeHtml(option.title)}</span>
                <strong>${option.mode === "new" ? "新增项目" : "已有项目"}</strong>
              </button>
            `,
          )
          .join("")
      : "";
    menu.classList.toggle("visible", projectSuggestionState.open);
  }

  function closeProjectSuggestions() {
    projectSuggestionState.open = false;
    $("#projectSuggestions")?.classList.remove("visible");
    $("#projectTitleInput")?.setAttribute("aria-expanded", "false");
  }

  function selectProjectOption(option, form) {
    const input = $("#projectTitleInput");
    const projectId = form.elements.projectId;
    const mode = form.elements.projectSelectionMode;
    input.value = option.title;
    mode.value = option.mode;
    if (option.mode === "existing" && option.project) {
      projectId.value = option.project.id;
      form.elements.projectSummary.value = option.project.summary || "";
      if (option.project.programId && option.project.programId !== "general_competition") {
        form.elements.programId.value = option.project.programId;
        applyProgramRules(form);
      }
      $("#projectSelectionMeta").textContent = `已有项目 · ${option.project.libraryYear || "项目库"} · ${option.project.college || "未标学院"}`;
    } else {
      projectId.value = "";
      $("#projectSelectionMeta").textContent = "新增项目 · 发布时会保存为独立项目记录。";
    }
    closeProjectSuggestions();
    renderPublishSummary(collectPublishDraft(form));
  }

  function renderCompetitionChecklist(selected = []) {
    const select = $("#competitionSelect");
    const container = $("#competitionChecklist");
    if (!select || !container) return;
    const selectedSet = new Set(selected);
    select.innerHTML = state.competitions.map((item) => `<option value="${escapeAttr(item.id)}">${escapeHtml(item.name)}</option>`).join("");
    setMultiValues(select, selected);
    container.innerHTML = state.competitions
      .map(
        (item) => `
          <label>
            <input type="checkbox" value="${escapeAttr(item.id)}" ${selectedSet.has(item.id) ? "checked" : ""} />
            ${escapeHtml(item.name)}
          </label>
        `,
      )
      .join("");
    container.onchange = () => {
      const values = getChecklistValues("competitionChecklist");
      setMultiValues(select, values);
      const first = state.competitions.find((item) => item.id === values[0]);
      const field = $("#publishForm")?.elements.competition;
      if (first && field && !field.value.trim()) field.value = first.name;
    };
  }

  function collectPublishDraft(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    data.requiredTags = getChecklistValues("publishTagChecklist");
    data.competitionIds = getChecklistValues("competitionChecklist");
    data.gradeMin = String(form.elements.gradeMin.value);
    data.gradeMax = String(form.elements.gradeMax.value);
    data.grades = gradeRangeToValues(data.gradeMin, data.gradeMax);
    return normalizeDraftData(data);
  }

  function normalizeDraftData(data = {}) {
    const normalized = { ...data };
    normalized.programId ||= "general_competition";
    normalized.projectId ||= "";
    normalized.projectTitle ||= normalized.competitionSubtitle || "";
    normalized.projectSelectionMode ||= normalized.projectId ? "existing" : "new";
    normalized.projectSummary ||= "";
    normalized.competition ||= "";
    normalized.competitionSubtitle ||= "";
    normalized.level ||= "国家";
    normalized.campus ||= "一校区";
    normalized.college ||= "";
    normalized.total ||= "3";
    normalized.current ||= "1";
    if ((normalized.gradeMin == null || normalized.gradeMax == null) && Array.isArray(normalized.grades) && normalized.grades.length) {
      const indexes = normalized.grades.map((grade) => GRADE_OPTIONS.indexOf(grade)).filter((index) => index >= 0);
      if (indexes.length) {
        normalized.gradeMin = String(Math.min(...indexes));
        normalized.gradeMax = String(Math.max(...indexes));
      }
    }
    normalized.gradeMin ??= "0";
    normalized.gradeMax ??= "5";
    if (!Array.isArray(normalized.requiredTags)) normalized.requiredTags = normalized.requiredTags ? [normalized.requiredTags] : [];
    if (!Array.isArray(normalized.competitionIds)) normalized.competitionIds = normalized.competitionIds ? [normalized.competitionIds] : [];
    normalized.teacherStatus ||= "不需要";
    normalized.teacherName ||= "";
    normalized.summary ||= "";
    normalized.requirement ||= "";
    normalized.deadline ||= "";
    normalized.smsCode ||= "";
    normalized.captcha ||= "";
    return normalized;
  }

  function saveDraftFromForm(form, silent = false) {
    const data = collectPublishDraft(form);
    const now = new Date().toISOString();
    if (!activeDraftId) activeDraftId = uid("draft");
    const existing = state.drafts.find((draft) => draft.id === activeDraftId);
    if (existing) {
      existing.data = data;
      existing.updatedAt = now;
    } else {
      state.drafts.unshift({ id: activeDraftId, data, updatedAt: now });
    }
    saveState();
    $("#draftState").textContent = `草稿已保存 ${formatTime(now)}`;
    if (!silent) {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
      renderDrafts();
      toast("草稿已保存到本地浏览器");
    }
    renderFieldErrors({});
    renderPublishSummary(data);
  }

  function scheduleDraftSave(form) {
    window.clearTimeout(draftSaveTimer);
    draftSaveTimer = window.setTimeout(() => {
      draftSaveTimer = 0;
      saveDraftFromForm(form, true);
    }, 600);
  }

  function loadDraftIntoForm(form, draftId = activeDraftId || state.drafts[0]?.id) {
    const draft = state.drafts.find((item) => item.id === draftId);
    if (!draft) {
      toast("没有可载入的草稿");
      return;
    }
    activeDraftId = draft.id;
    const data = normalizeDraftData(draft.data);
    Object.entries(data).forEach(([key, value]) => {
      const field = form.elements[key];
      if (!field) return;
      if (field instanceof RadioNodeList || field.tagName === "SELECT" && field.multiple) return;
      field.value = value;
    });
    setChecklistValues("publishTagChecklist", data.requiredTags || []);
    renderCompetitionChecklist(data.competitionIds || []);
    $("#projectSelectionMeta").textContent = data.projectSelectionMode === "existing" ? "已有项目 · 草稿已绑定项目库记录。" : "新增项目 · 发布时会保存为独立项目记录。";
    applyProgramRules(form);
    updateGradeRangeLabel(form);
    renderFieldErrors({});
    renderPublishSummary(data);
    renderDrafts();
    toast("草稿已载入");
  }

  function createNewDraft(form) {
    activeDraftId = uid("draft");
    form.reset();
    setDefaultDeadline();
    form.elements.gradeMin.value = "0";
    form.elements.gradeMax.value = "5";
    clearChecklist("publishTagChecklist");
    updateGradeRangeLabel(form);
    saveDraftFromForm(form, true);
    form.elements.competition.focus();
    toast("新草稿已创建");
  }

  function deleteDraft(draftId) {
    if (!confirm("确定删除这个草稿吗？")) return;
    state.drafts = state.drafts.filter((draft) => draft.id !== draftId);
    if (activeDraftId === draftId) activeDraftId = state.drafts[0]?.id || null;
    saveState();
    renderDrafts();
    toast("草稿已删除");
  }

  function bindGradeRange(form) {
    ["gradeMin", "gradeMax"].forEach((name) => {
      form.elements[name].addEventListener("input", () => updateGradeRangeLabel(form));
    });
    updateGradeRangeLabel(form);
  }

  function updateGradeRangeLabel(form) {
    let min = Number(form.elements.gradeMin.value);
    let max = Number(form.elements.gradeMax.value);
    if (min > max) {
      [min, max] = [max, min];
      form.elements.gradeMin.value = String(min);
      form.elements.gradeMax.value = String(max);
    }
    $("#gradeRangeLabel").textContent = formatGradeRange(min, max);
    renderPublishSummary(collectPublishDraft(form));
  }

  function gradeRangeToValues(min, max) {
    const left = Math.min(Number(min) || 0, Number(max) || 0);
    const right = Math.max(Number(min) || 0, Number(max) || 0);
    return GRADE_OPTIONS.slice(left, right + 1);
  }

  function formatGradeRange(min, max) {
    const left = Math.min(Number(min) || 0, Number(max) || 0);
    const right = Math.max(Number(min) || 0, Number(max) || 0);
    if (left === 0 && right === GRADE_OPTIONS.length - 1) return "不限";
    if (left === right) return GRADE_OPTIONS[left];
    return `${GRADE_OPTIONS[left]}至${GRADE_OPTIONS[right]}`;
  }

  function validatePublishDraft(data) {
    const errors = {};
    const total = Number(data.total);
    const current = Number(data.current);
    const program = programById(data.programId);
    if (!String(data.projectTitle || "").trim()) errors.projectTitle = "请选择已有项目或输入新项目题目";
    if (!String(data.competition || "").trim() && !data.competitionIds?.length) errors.competition = "请填写或选择至少一个关联竞赛";
    if (!Number.isFinite(total) || total < 1) errors.total = "总人数至少为 1";
    if (!Number.isFinite(current) || current < 1) errors.current = "已有人数至少为 1";
    if (Number.isFinite(total) && Number.isFinite(current) && current > total) errors.current = "已有人数不能超过总人数";
    if (program.eligibleGrades?.length && !program.eligibleGrades.every((grade) => data.grades.includes(grade))) {
      errors.gradeMin = `${program.name}仅限${program.eligibleGrades.join("、")}`;
    }
    if (!data.requiredTags.length) errors.requiredTags = "至少选择 1 个技能标签";
    if (!String(data.summary || "").trim()) errors.summary = "请填写团队标签简介";
    if (!String(data.requirement || "").trim()) errors.requirement = "请填写招募要求";
    const deadline = new Date(String(data.deadline));
    if (!data.deadline || Number.isNaN(deadline.getTime())) errors.deadline = "请设置截止时间";
    else if (deadline.getTime() <= Date.now()) errors.deadline = "截止时间不能早于当前时间";
    if (!/^\d{4,6}$/.test(String(data.smsCode || ""))) errors.smsCode = "短信验证码需为 4-6 位数字";
    if (String(data.captcha || "").trim().toUpperCase() !== "HIT") errors.captcha = "行为验证码请输入 HIT";
    return errors;
  }

  function renderFieldErrors(errors) {
    $$("[data-error-for]").forEach((node) => {
      node.textContent = errors[node.dataset.errorFor] || "";
    });
  }

  function renderPublishSummary(data) {
    const summary = $("#publishSummary");
    if (!summary) return;
    const title = data.projectTitle || "未填写项目题目";
    const tags = data.requiredTags.length ? data.requiredTags.join("、") : "未选择";
    const program = programById(data.programId);
    const linked = data.competitionIds?.map((id) => state.competitions.find((item) => item.id === id)?.name).filter(Boolean) || [];
    summary.innerHTML = `
      <h4>发布前摘要</h4>
      <div class="summary-grid">
        <div class="summary-item"><span>项目类型</span><strong>${escapeHtml(program.name)}</strong></div>
        <div class="summary-item"><span>项目题目</span><strong>${escapeHtml(title)}</strong></div>
        <div class="summary-item"><span>关联竞赛</span><strong>${escapeHtml(linked.join("、") || data.competition || "未填写")}</strong></div>
        <div class="summary-item"><span>人数</span><strong>${escapeHtml(data.current || "0")} / ${escapeHtml(data.total || "0")}</strong></div>
        <div class="summary-item"><span>年级</span><strong>${escapeHtml(formatGradeRange(data.gradeMin, data.gradeMax))}</strong></div>
        <div class="summary-item"><span>标签</span><strong>${escapeHtml(tags)}</strong></div>
        <div class="summary-item"><span>截止</span><strong>${escapeHtml(formatDraftDeadline(data.deadline))}</strong></div>
      </div>
      <p class="file-meta">联系方式仍按双方隐私设置在匹配通过后释放。</p>
    `;
  }

  function formatDraftDeadline(value) {
    const date = new Date(String(value || ""));
    if (!value || Number.isNaN(date.getTime())) return "未设置";
    return formatTime(date.toISOString());
  }

  function bindProfile() {
    const form = $("#profileForm");
    $("#profileForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const user = currentUser();
      const avatarFile = form.elements.avatarFile.files?.[0];
      if (avatarFile) {
        user.avatar = await readSingleFileAsDataUrl(avatarFile);
        state.files.push(fileRecord(avatarFile, "profile", user.avatar));
      }
      user.nickname = String(data.get("nickname")).trim();
      user.realName = String(data.get("realName") || "").trim();
      user.realNameVisibility = String(data.get("realNameVisibility"));
      user.campus = String(data.get("campus"));
      user.college = String(data.get("college")).trim();
      user.major = String(data.get("major")).trim();
      user.grade = String(data.get("grade") || "大二");
      user.contact = String(data.get("contact") || "").trim();
      user.contactVisibility = String(data.get("contactVisibility"));
      user.tags = getChecklistValues("profileTagChecklist");
      user.bio = String(data.get("bio") || "").trim();
      saveState();
      renderAll();
      toast("能力档案已保存");
    });
    $("#previewOwnResume")?.addEventListener("click", () => openResumePreview(CURRENT_USER_ID));
  }

  function bindAwards() {
    const form = $("#awardForm");
    form.addEventListener("input", renderAwardPreview);
    form.addEventListener("change", renderAwardPreview);
    $("#awardForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const award = awardFromForm(form);
      currentUser().awards.unshift(award);
      const duplicate = duplicateAwardHint(currentUser(), award);
      form.reset();
      saveState();
      renderProfile();
      renderAwardPreview();
      toast(duplicate || "竞赛履历已添加");
    });
    $("#awardList").addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-award]");
      if (!button) return;
      currentUser().awards = currentUser().awards.filter((item) => item.id !== button.dataset.deleteAward);
      saveState();
      renderProfile();
    });
  }

  function awardFromForm(form) {
    const data = new FormData(form);
    return {
      id: uid("award"),
      name: String(data.get("name")).trim(),
      shortName: String(data.get("shortName") || "").trim() || shortNameForAward(data.get("name")),
      year: Number(data.get("year")) || new Date().getFullYear(),
      level: String(data.get("level")),
      role: String(data.get("role")),
      award: String(data.get("award")),
      solo: data.get("solo") === "on",
    };
  }

  function renderAwardPreview() {
    const form = $("#awardForm");
    const preview = $("#awardPreview");
    if (!form || !preview) return;
    const award = awardFromForm(form);
    const duplicate = duplicateAwardHint(currentUser(), award);
    preview.textContent = `奖项标签预览：${award.shortName || "竞赛简称"} ${awardText(award.award)}${duplicate ? `；${duplicate}` : ""}`;
  }

  function duplicateAwardHint(user, award) {
    if (!award.name || !award.year) return "";
    const same = (user.awards || []).filter(
      (item) => item.id !== award.id && String(item.name).trim().toLowerCase() === String(award.name).trim().toLowerCase() && Number(item.year) === Number(award.year),
    );
    if (!same.length) return "";
    return "同年同赛事已有记录，请确认是否重复添加";
  }

  function bindAdmin() {
    $("#tagAdminForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const input = event.currentTarget.elements.tagName;
      const name = input.value.trim();
      if (!name) return;
      if (state.tags.some((tag) => tag.name === name)) {
        toast("标签已存在", "error");
        return;
      }
      state.tags.push({ id: uid("tag"), name, status: "official", createdAt: new Date().toISOString() });
      input.value = "";
      saveState();
      renderAll();
      toast("标签已添加");
    });
    $("#competitionAdminForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const name = form.elements.competitionName.value.trim();
      if (!name) return;
      state.competitions.push({
        id: uid("c"),
        name,
        level: form.elements.competitionLevel.value,
      });
      form.reset();
      saveState();
      renderAll();
      toast("竞赛已添加");
    });
    $("#projectAdminForm")?.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!canManageContent(currentRole())) {
        toast("只有系统管理员或平台创建者可以维护项目库", "error");
        return;
      }
      const form = event.currentTarget;
      const title = form.elements.projectTitle.value.trim();
      if (!title) return;
      state.projects.push({
        id: uid("project"),
        programId: form.elements.projectProgramId.value,
        title,
        summary: form.elements.projectSummary.value.trim(),
        source: "library",
        libraryYear: `${new Date().getFullYear()}项目库`,
        college: "",
        advisor: "",
        interdisciplinary: false,
        active: true,
      });
      form.reset();
      saveState();
      renderAll();
      toast("项目已加入项目库");
    });
    $("#adminTags").addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-tag]");
      if (!button) return;
      state.tags = state.tags.filter((tag) => tag.id !== button.dataset.deleteTag);
      saveState();
      renderAll();
    });
    $("#adminCompetitions").addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-competition]");
      if (!button) return;
      state.competitions = state.competitions.filter((item) => item.id !== button.dataset.deleteCompetition);
      saveState();
      renderAll();
    });
    $("#adminProjects")?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-project]");
      if (!button) return;
      if (!canManageContent(currentRole())) {
        toast("只有系统管理员或平台创建者可以维护项目库", "error");
        return;
      }
      const project = projectById(button.dataset.deleteProject);
      if (!project) return;
      project.active = false;
      saveState();
      renderAll();
      toast("项目已停用");
    });
    $("#adminUsers")?.addEventListener("click", (event) => {
      const appoint = event.target.closest("[data-appoint-admin]");
      const revoke = event.target.closest("[data-revoke-admin]");
      if (!appoint && !revoke) return;
      if (!canManageAdmins(currentRole())) {
        toast("只有平台创建者可以任免管理员", "error");
        return;
      }
      const id = appoint?.dataset.appointAdmin || revoke?.dataset.revokeAdmin;
      const user = userById(id);
      if (!user || id === state.platform.creatorId) return;
      const appointing = Boolean(appoint);
      user.systemRole = appointing ? "admin" : null;
      state.platform.adminIds = state.users.filter((item) => item.systemRole === "admin").map((item) => item.id);
      state.platform.auditLog.unshift({
        id: uid("audit"),
        action: appointing ? "appoint_admin" : "revoke_admin",
        targetId: id,
        operator: currentUser().nickname,
        createdAt: new Date().toISOString(),
      });
      saveState();
      renderAll();
      toast(appointing ? "已任命系统管理员" : "已撤销系统管理员");
    });
    $("#customTagReview").addEventListener("click", (event) => {
      const approve = event.target.closest("[data-approve-tag]");
      const reject = event.target.closest("[data-reject-tag]");
      if (!approve && !reject) return;
      const id = approve?.dataset.approveTag || reject?.dataset.rejectTag;
      const item = state.customTags.find((tag) => tag.id === id);
      if (!item) return;
      item.status = approve ? "approved" : "rejected";
      if (approve && !state.tags.some((tag) => tag.name === item.name)) {
        state.tags.push({ id: uid("tag"), name: item.name, status: "official", createdAt: new Date().toISOString() });
      }
      saveState();
      renderAll();
    });
    $("#reportList").addEventListener("click", (event) => {
      const button = event.target.closest("[data-resolve-report]");
      if (!button) return;
      const report = state.reports.find((item) => item.id === button.dataset.resolveReport);
      if (report) report.status = "resolved";
      saveState();
      renderAdmin();
    });
  }

  function bindFiles() {
    $("#exportAll").addEventListener("click", exportData);
    $("#exportData").addEventListener("click", exportData);
    $("#saveSnapshot").addEventListener("click", exportData);
    $("#importData").addEventListener("change", importData);
    $("#clearData").addEventListener("click", () => {
      if (!confirm("确定清空本地数据吗？此操作只影响当前浏览器。")) return;
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(DRAFT_KEY);
      state = ensureStateShape(demoState());
      saveState();
      renderAll();
      toast("本地数据已清空并重建演示数据");
    });
    $("#resetDemo").addEventListener("click", () => {
      if (!confirm("恢复演示数据会覆盖当前原型数据，继续吗？")) return;
      state = ensureStateShape(demoState());
      saveState();
      renderAll();
      toast("演示数据已恢复");
    });
    $("#libraryFiles").addEventListener("change", (event) => {
      pendingLibraryFiles = Array.from(event.target.files || []);
      $("#libraryFileState").textContent = pendingLibraryFiles.length
        ? `已选择 ${pendingLibraryFiles.length} 个文件，约 ${formatBytes(pendingLibraryFiles.reduce((sum, file) => sum + file.size, 0))}`
        : "未选择文件";
    });
    $("#storeFiles").addEventListener("click", async () => {
      if (!pendingLibraryFiles.length) {
        toast("请选择文件");
        return;
      }
      const scope = $("#fileScope").value;
      const files = await readFiles(pendingLibraryFiles, scope);
      state.files.push(...files);
      pendingLibraryFiles = [];
      $("#libraryFiles").value = "";
      $("#libraryFileState").textContent = "未选择文件";
      saveState();
      renderFiles();
      toast("文件已保存到本地库");
    });
    $("#fileLibrary").addEventListener("click", (event) => {
      const remove = event.target.closest("[data-delete-file]");
      const download = event.target.closest("[data-download-file]");
      if (remove) {
        state.files = state.files.filter((file) => file.id !== remove.dataset.deleteFile);
        saveState();
        renderFiles();
      }
      if (download) {
        const file = state.files.find((item) => item.id === download.dataset.downloadFile);
        if (file?.dataUrl) downloadDataUrl(file);
        else toast("该文件只保存了元数据，无法下载原文件", "error");
      }
    });
  }

  function bindGlobalActions() {
    $("#recruitmentList").addEventListener("click", (event) => {
      const detail = event.target.closest("[data-detail]");
      const resume = event.target.closest("[data-resume]");
      const apply = event.target.closest("[data-apply]");
      const review = event.target.closest("[data-open-review]");
      const progress = event.target.closest("[data-open-progress]");
      if (detail) openDetail(detail.dataset.detail);
      if (resume) openResumePreview(resume.dataset.resume);
      if (apply) openDetail(apply.dataset.apply, true);
      if (review) showView("mine", { step: "review" });
      if (progress) showView("messages", { step: "apply" });
    });
    $("#detailDialog").addEventListener("click", (event) => {
      const apply = event.target.closest("[data-submit-application]");
      const resume = event.target.closest("[data-resume]");
      if (apply) submitApplication(apply.dataset.submitApplication);
      if (resume) openResumePreview(resume.dataset.resume);
    });
    $("#myRecruitments").addEventListener("click", (event) => {
      const close = event.target.closest("[data-close-recruitment]");
      if (!close) return;
      const item = state.recruitments.find((rec) => rec.id === close.dataset.closeRecruitment);
      if (!item) return;
      item.status = "closed";
      addMessage("notification", "招募已关闭", `${item.competition} 不再接收新申请。`);
      saveState();
      renderAll();
    });
    $("#applicationReview").addEventListener("click", (event) => {
      const resume = event.target.closest("[data-resume]");
      if (resume) {
        openResumePreview(resume.dataset.resume);
        return;
      }
      const approve = event.target.closest("[data-approve-app]");
      const reject = event.target.closest("[data-reject-app]");
      if (!approve && !reject) return;
      if (currentRole() !== "captain") {
        toast("请先切换到队长身份", "error");
        return;
      }
      reviewApplication(approve?.dataset.approveApp || reject?.dataset.rejectApp, Boolean(approve));
    });
    $("#markRead").addEventListener("click", () => {
      [...state.messages, ...state.conversations].forEach((item) => {
        item.read = true;
      });
      saveState();
      renderMessages();
    });
    $("#conversationList").addEventListener("click", async (event) => {
      const button = event.target.closest("[data-copy-contact]");
      if (!button) return;
      const value = button.dataset.copyContact;
      try {
        await navigator.clipboard.writeText(value);
        button.textContent = "已复制";
        setTimeout(() => {
          button.textContent = "复制联系方式";
        }, 1600);
        toast("联系方式已复制");
      } catch {
        toast(value);
      }
    });
    $("#collaborationList").addEventListener("click", async (event) => {
      const copy = event.target.closest("[data-copy-collab-contact]");
      const openFiles = event.target.closest("[data-open-collab-files]");
      const detail = event.target.closest("[data-detail]");
      const jump = event.target.closest("[data-view-jump]");
      if (copy) {
        const value = copy.dataset.copyCollabContact;
        try {
          await navigator.clipboard.writeText(value);
          copy.textContent = "已复制";
          setTimeout(() => {
            copy.textContent = "复制联系卡";
          }, 1600);
          toast("联系卡已复制");
        } catch {
          toast(value);
        }
      }
      if (detail) openDetail(detail.dataset.detail);
      if (openFiles) showView("files", { step: "collaborate" });
      if (jump) showView(jump.dataset.viewJump, { step: jump.dataset.stepJump || jump.dataset.step });
    });
    $("#collaborationFileList").addEventListener("click", (event) => {
      const openFiles = event.target.closest("[data-open-collab-files]");
      if (openFiles) showView("files", { step: "collaborate" });
    });
    $("#collaborationList").addEventListener("change", (event) => {
      const task = event.target.closest("[data-collab-task]");
      const meeting = event.target.closest("[data-collab-meeting]");
      if (task) updateCollaborationTask(task.dataset.collabKey, task.dataset.collabTask, task.checked);
      if (meeting) updateCollaborationField(meeting.dataset.collabKey, "meetingAt", meeting.value);
    });
    $("#collaborationList").addEventListener("input", (event) => {
      const note = event.target.closest("[data-collab-note]");
      if (note) updateCollaborationField(note.dataset.collabKey, "note", note.value, false);
    });
    $("#collaborationList").addEventListener("focusout", (event) => {
      const note = event.target.closest("[data-collab-note]");
      if (note) {
        updateCollaborationField(note.dataset.collabKey, "note", note.value);
        toast("协作备注已保存");
      }
    });
    $("#exportProfile").addEventListener("click", () => {
      downloadJson(currentUser(), `hiteam-profile-${safeDate()}.json`);
    });
  }

  function renderAll() {
    renderUiState();
    renderOptions();
    renderDrafts();
    renderFilterTags();
    renderMetrics();
    renderSession();
    renderRecruitments();
    renderProfile();
    renderMine();
    renderMessages();
    renderCollaboration();
    renderAdmin();
    renderFiles();
  }

  function renderUiState() {
    const role = currentRole();
    const step = currentTaskStep();
    $$("#roleSwitch [data-role]").forEach((button) => {
      button.classList.toggle("active", button.dataset.role === role);
    });
    $$(".task-step").forEach((button) => {
      button.classList.toggle("active", button.dataset.step === step);
    });
    $$(".nav-item, .mobile-nav").forEach((button) => {
      button.classList.toggle("active", button.dataset.step === step);
    });
    const advanced = $("#advancedTools");
    const toggle = $("#toggleAdvanced");
    advanced?.classList.toggle("hidden", !state.ui.advancedOpen);
    if (toggle) {
      toggle.textContent = state.ui.advancedOpen ? "收起高级工具" : "高级工具";
      toggle.setAttribute("aria-expanded", String(Boolean(state.ui.advancedOpen)));
    }
    const readiness = profileReadiness(currentUser());
    $("#profileReadiness").textContent = readiness.label;
    $("#applicationProgress").textContent = applicationProgressLabel();
    $("#captainQueue").textContent = `待审 ${pendingReviewCount()}`;
    $("#collaborationProgress").textContent = collaborationProgressLabel();
    document.body.dataset.role = role;
    document.body.dataset.step = step;
    document.documentElement.dataset.theme = state.ui.theme || "light";
    const themeButton = $("#toggleTheme");
    if (themeButton) {
      themeButton.textContent = state.ui.theme === "dark" ? "浅色" : "深色";
      themeButton.setAttribute("aria-label", state.ui.theme === "dark" ? "切换浅色模式" : "切换深色模式");
    }
  }

  function renderSession() {
    const user = currentUser();
    $("#sessionName").textContent = user.nickname;
    $("#sessionMeta").textContent = `${ROLE_LABELS[currentRole()]} · ${user.grade || "未填写年级"} · ${user.campus}`;
  }

  function renderMetrics() {
    const openCount = state.recruitments.filter((item) => item.status === "open").length;
    const pending = state.recruitments
      .filter((item) => item.publisherId === CURRENT_USER_ID)
      .flatMap((item) => item.applications || [])
      .filter((app) => app.status === "pending").length;
    const matched = state.recruitments
      .flatMap((item) => item.applications || [])
      .filter((app) => app.status === "accepted").length;
    $("#metricOpen").textContent = openCount;
    $("#metricPending").textContent = pending;
    $("#metricMatched").textContent = matched;
    $("#metricPrograms").textContent = new Set(state.recruitments.map((item) => item.programId || "general_competition")).size;
  }

  function userApplications(userId = CURRENT_USER_ID) {
    return state.recruitments.flatMap((recruitment) =>
      (recruitment.applications || [])
        .filter((application) => application.userId === userId)
        .map((application) => ({ recruitment, application })),
    );
  }

  function pendingReviewCount() {
    return state.recruitments
      .filter((item) => item.publisherId === CURRENT_USER_ID)
      .flatMap((item) => item.applications || [])
      .filter((app) => app.status === "pending").length;
  }

  function applicationProgressLabel() {
    const apps = userApplications();
    const pending = apps.filter(({ application }) => application.status === "pending").length;
    const accepted = apps.filter(({ application }) => application.status === "accepted").length;
    if (accepted && pending) return `已通过 ${accepted} / 待审 ${pending}`;
    if (accepted) return `已通过 ${accepted}`;
    if (pending) return `待审核 ${pending}`;
    return "待申请";
  }

  function collaborationProgressLabel() {
    const contactCards = state.conversations.filter((item) => item.contact).length;
    const accepted = userApplications().filter(({ application }) => application.status === "accepted").length;
    if (contactCards) return `联系卡 ${contactCards}`;
    if (accepted) return `已匹配 ${accepted}`;
    return "匹配后开放";
  }

  function profileReadiness(user) {
    const checks = [
      ["昵称", user.nickname],
      ["校区", user.campus],
      ["学院", user.college],
      ["专业", user.major],
      ["年级", user.grade],
      ["联系方式", user.contact],
      ["个人标签", user.tags?.length],
    ];
    const missing = checks.filter(([, value]) => !value).map(([label]) => label);
    const complete = checks.length - missing.length;
    return {
      complete,
      total: checks.length,
      missing,
      ready: missing.length <= 1,
      label: missing.length ? `完成 ${complete}/${checks.length}` : "可申请",
    };
  }

  function renderOptions() {
    const competitionOptions = state.competitions
      .map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.level)}</option>`)
      .join("");
    $("#competitionDatalist").innerHTML = competitionOptions;
    const tagOptions = state.tags
      .map((tag) => `<option value="${escapeHtml(tag.name)}">${escapeHtml(tag.name)}</option>`)
      .join("");
    $("#publishTagSelect").innerHTML = tagOptions;
    $("#profileTagSelect").innerHTML = tagOptions;
    setMultiValues($("#profileTagSelect"), currentUser().tags || []);
    renderCheckboxGrid("publishTagChecklist", state.tags, getChecklistValues("publishTagChecklist"));
    renderCheckboxGrid("profileTagChecklist", state.tags, currentUser().tags || []);
    setChecklistValues("profileTagChecklist", currentUser().tags || []);
    const draft = activeDraftId ? state.drafts.find((item) => item.id === activeDraftId)?.data : null;
    renderCompetitionChecklist(normalizeDraftData(draft || {}).competitionIds || []);
  }

  function renderDrafts() {
    const drafts = state.drafts || [];
    $("#draftCount").textContent = `${drafts.length} 个草稿`;
    $("#draftPreviewList").innerHTML = drafts.length
      ? drafts.map(draftCard).join("")
      : `<div class="list-item"><h5>暂无草稿</h5><p class="file-meta">点击“新建草稿”开始。</p></div>`;
  }

  function draftCard(draft) {
    const data = normalizeDraftData(draft.data);
    const active = draft.id === activeDraftId ? " active" : "";
    const title = data.competition || "未命名招募";
    const subtitle = data.projectTitle || data.competitionSubtitle || data.summary || "未填写项目题目";
    const grades = formatGradeRange(data.gradeMin, data.gradeMax);
    return `
      <article class="draft-card${active}">
        <header>
          <div>
            <h5>${escapeHtml(title)}</h5>
            <p>${escapeHtml(subtitle)}</p>
          </div>
          <span class="status-pill ${active ? "open" : "closed"}">${active ? "编辑中" : "草稿"}</span>
        </header>
        <p>${escapeHtml(programById(data.programId).name)} · ${escapeHtml(data.campus)} · ${escapeHtml(grades)} · ${formatTime(draft.updatedAt)}</p>
        <div class="item-actions">
          <button class="ghost-button" type="button" data-load-draft="${draft.id}">载入</button>
          <button class="ghost-button danger" type="button" data-delete-draft="${draft.id}">删除</button>
        </div>
      </article>
    `;
  }

  function renderCheckboxGrid(containerId, tags, selected) {
    const selectedSet = new Set(selected || []);
    const container = $(`#${containerId}`);
    if (!container) return;
    container.innerHTML = tags
      .map(
        (tag) => `
          <label>
            <input type="checkbox" value="${escapeAttr(tag.name)}" ${selectedSet.has(tag.name) ? "checked" : ""} />
            ${escapeHtml(tag.name)}
          </label>
        `,
      )
      .join("");
  }

  function renderFilterTags() {
    $("#filterTags").innerHTML = state.tags
      .map((tag) => {
        const selected = selectedFilterTags.has(tag.name) ? " selected" : "";
        return `<button class="chip${selected}" type="button" data-filter-tag="${escapeAttr(tag.name)}">${escapeHtml(tag.name)}</button>`;
      })
      .join("");
    $$("#filterTags [data-filter-tag]").forEach((button) => {
      button.addEventListener("click", () => {
        const tag = button.dataset.filterTag;
        if (selectedFilterTags.has(tag)) selectedFilterTags.delete(tag);
        else selectedFilterTags.add(tag);
        renderFilterTags();
        renderRecruitments();
      });
    });
  }

  function renderRecruitments() {
    const items = filteredRecruitments();
    $("#resultCount").textContent = `${items.length} 条结果`;
    $("#recruitmentList").innerHTML = items.length
      ? items.map((item) => recruitmentCard(item)).join("")
      : `<div class="list-item"><h5>没有匹配的招募</h5><p class="file-meta">调整筛选条件或发布新的招募。</p></div>`;
  }

  function explainMatch(item, user = currentUser()) {
    const tags = item.tags || [];
    const userTags = user.tags || [];
    const matchedTags = tags.filter((tag) => userTags.includes(tag));
    const missingTags = tags.filter((tag) => !userTags.includes(tag));
    const slots = Math.max(0, remainingSlots(item));
    const hoursLeft = Math.round((new Date(item.deadline).getTime() - Date.now()) / 36e5);
    const deadlineText = hoursLeft < 0 ? "已截止" : hoursLeft <= 72 ? `${Math.max(1, hoursLeft)} 小时内截止` : `${Math.ceil(hoursLeft / 24)} 天后截止`;
    const locality =
      item.campus === user.campus && item.college === user.college
        ? "同校区同学院"
        : item.campus === user.campus
          ? "同校区"
          : `${item.campus} 可跨校区沟通`;
    const program = programById(item.programId);
    const qualified = !program.eligibleGrades?.length || program.eligibleGrades.includes(user.grade);
    const project = projectById(item.projectId);
    const competitionNames = (item.competitionIds || [])
      .map((id) => state.competitions.find((competition) => competition.id === id)?.name)
      .filter(Boolean);
    return {
      matchedTags,
      missingTags,
      slots,
      deadlineText,
      locality,
      qualified,
      program,
      project,
      competitionNames,
      fit: matchedTags.length + (qualified ? 2 : 0) + (slots > 0 ? 1 : 0),
      summary: [
        matchedTags.length ? `与你的 ${matchedTags.join("、")} 能力标签重合` : "暂未找到直接重合的能力标签",
        missingTags.length ? `还缺 ${missingTags.slice(0, 2).join("、")}` : "技能完全覆盖",
        qualified ? `你符合${program.name}的年级资格` : `${program.name}要求${program.eligibleGrades?.join("、") || "指定年级"}`,
        locality,
        slots ? `剩余 ${slots} 个名额` : "队伍已满",
        competitionNames.length > 1 ? `同一项目可复用至：${competitionNames.slice(0, 2).join("、")}` : competitionNames[0] ? `关联竞赛：${competitionNames[0]}` : "可在详情中补充关联竞赛",
        deadlineText,
      ],
    };
  }

  function actionState(item, role = currentRole()) {
    const alreadyApplied = hasApplied(item, CURRENT_USER_ID);
    const full = remainingSlots(item) <= 0;
    if (item.publisherId === CURRENT_USER_ID) {
      const pending = (item.applications || []).some((application) => application.status === "pending");
      if (role === "captain" && pending) {
        return {
          kind: "review",
          label: "去审核",
          reason: "这是你发布的招募，当前有待处理申请。",
          next: "进入队长审核处理申请。",
        };
      }
      return {
        kind: "detail",
        label: role === "captain" ? "暂无待审" : "自己的招募",
        reason: "这是你发布的招募，申请入口已隐藏。",
        next: role === "captain" ? "可查看详情或在队长审核页管理招募。" : "切换到队长身份后再处理审核任务。",
      };
    }
    if (alreadyApplied) {
      return {
        kind: "progress",
        label: "查看进度",
        reason: "你已提交过申请，避免重复申请。",
        next: "到申请进度中心查看结果。",
      };
    }
    if (item.status !== "open") {
      return {
        kind: "blocked",
        label: statusText(item.status),
        reason: item.status === "expired" ? "报名时间已过，申请入口关闭。" : "队长已关闭招募。",
        next: "查看详情或换一个仍在招募的队伍。",
      };
    }
    if (full) {
      return {
        kind: "blocked",
        label: "已满员",
        reason: "队伍名额已满，申请入口隐藏。",
        next: "关注同类标签的其他招募。",
      };
    }
    if (role === "captain") {
      return {
        kind: "detail",
        label: "查看详情",
        reason: "队长身份下优先处理自己的审核任务。",
        next: "切回申请者身份后再申请其他队伍。",
      };
    }
    if (role === "admin") {
      return {
        kind: "detail",
        label: "查看详情",
        reason: "管理员身份只查看与维护，不提交申请。",
        next: "需要申请时切回申请者身份。",
      };
    }
    return {
      kind: "apply",
      label: "申请",
      reason: "当前可申请。",
      next: "提交技能、时间投入和可承担工作。",
    };
  }

  function recruitmentCard(item) {
    const publisher = userById(item.publisherId);
    const match = explainMatch(item);
    const status = statusText(item.status);
    const action = actionState(item);
    const actionMarkup =
      action.kind === "apply"
        ? `<button class="primary-button" type="button" data-apply="${item.id}">${action.label}</button>`
        : action.kind === "review"
            ? `<button class="primary-button" type="button" data-open-review="${item.id}">${action.label}</button>`
            : action.kind === "progress"
              ? `<button class="primary-button" type="button" data-open-progress="${item.id}">${action.label}</button>`
            : action.kind === "detail"
              ? `<div class="action-note"><strong>${escapeHtml(action.label)}</strong><span>${escapeHtml(action.reason)}</span></div>`
              : `<div class="action-note"><strong>${escapeHtml(action.label)}</strong><span>${escapeHtml(action.reason)}</span></div>`;
    return `
      <article class="recruitment-card${compactMode ? " compact" : ""}">
        <div>
            <div class="recruitment-title">
              <span class="avatar">${avatarMarkup(publisher)}</span>
            <h4>${escapeHtml(match.program.name)}</h4>
            <span class="status-pill ${item.status}">${status}</span>
          </div>
          <p class="recruitment-subtitle">${escapeHtml(item.projectTitle || item.competitionSubtitle || "未命名项目")}</p>
          <div class="recruitment-meta">
            <span>${escapeHtml(item.competition || "未指定竞赛")}</span>
            <span>${escapeHtml(item.campus)}</span>
            <span>${escapeHtml(item.college)}</span>
            <span>${item.current}/${item.total} 人</span>
            <span>截止 ${formatTime(item.deadline)}</span>
          </div>
          <div class="linked-competitions">${match.competitionNames.map((name) => `<span class="chip">${escapeHtml(name)}</span>`).join("")}</div>
          <p class="recruitment-summary">${escapeHtml(item.summary)}</p>
          <div class="card-tags">${(item.tags || []).map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}</div>
          <div class="match-explain">
            <strong>为什么推荐</strong>
            <div>${match.summary.map((line) => `<span>${escapeHtml(line)}</span>`).join("")}</div>
          </div>
        </div>
        ${compactMode ? `<p class="recruitment-summary">${escapeHtml(item.requirement)}</p>` : ""}
        <div class="card-actions">
          <button class="ghost-button" type="button" data-resume="${item.publisherId}">预览简历</button>
          <button class="ghost-button" type="button" data-detail="${item.id}">详情</button>
          ${actionMarkup}
          <p class="next-step">${escapeHtml(action.next)}</p>
        </div>
      </article>
    `;
  }

  function filteredRecruitments() {
    const form = $("#filterForm");
    const search = $("#filterSearch").value.trim().toLowerCase();
    const campus = $("#filterCampus").value;
    const programId = $("#filterProgram")?.value || "";
    const college = $("#filterCollege").value.trim().toLowerCase();
    const status = $("#filterStatus").value;
    const grade = $("#filterGrade").value;
    const sort = $("#filterSort").value;
    const tagLogic = new FormData(form).get("tagLogic") || "or";
    const selected = Array.from(selectedFilterTags);
    let items = [...state.recruitments];

    items = items.filter((item) => {
      const haystack = [
        item.competition,
        item.competitionSubtitle,
        item.projectTitle,
        programById(item.programId).name,
        item.level,
        item.campus,
        item.college,
        item.summary,
        item.requirement,
        ...(item.tags || []),
      ]
        .join(" ")
        .toLowerCase();
      const tagMatch =
        !selected.length ||
        (tagLogic === "and"
          ? selected.every((tag) => item.tags?.includes(tag))
          : selected.some((tag) => item.tags?.includes(tag)));
      return (
        (!search || haystack.includes(search)) &&
        (!campus || item.campus === campus) &&
        (!programId || item.programId === programId) &&
        (!college || item.college.toLowerCase().includes(college)) &&
        (!status || item.status === status) &&
        (!grade || item.grades?.includes(grade) || item.grades?.includes("不限")) &&
        tagMatch
      );
    });

    items.sort((a, b) => {
      const statusDelta = statusWeight(a.status) - statusWeight(b.status);
      if (!status && statusDelta !== 0) return statusDelta;
      if (sort === "match") return overlap(currentUser().tags, b.tags) - overlap(currentUser().tags, a.tags);
      return new Date(a.deadline) - new Date(b.deadline);
    });
    return items;
  }

  function openDetail(id, focusApply = false) {
    const item = state.recruitments.find((rec) => rec.id === id);
    if (!item) return;
    const publisher = userById(item.publisherId);
    const action = actionState(item);
    const match = explainMatch(item);
    const canApply = action.kind === "apply";
    const linkedCompetitions = match.competitionNames.length ? match.competitionNames.join("、") : item.competition || "未指定";
    $("#detailContent").innerHTML = `
      <div class="dialog-content">
        <span class="eyebrow">${escapeHtml(match.program.name)}</span>
        <h3>${escapeHtml(item.projectTitle || item.competition)}</h3>
        <p class="recruitment-subtitle">关联竞赛：${escapeHtml(linkedCompetitions)}</p>
        <div class="recruitment-meta">
          <span>${escapeHtml(item.campus)}</span>
          <span>${escapeHtml(item.college)}</span>
          <span>${item.current}/${item.total} 人</span>
          <span>${statusText(item.status)}</span>
        </div>
        <div class="card-tags">${(item.tags || []).map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}</div>
        <div class="match-explain detail-explain">
          <strong>匹配解释</strong>
          <div>${match.summary.map((line) => `<span>${escapeHtml(line)}</span>`).join("")}</div>
        </div>
        <p>${escapeHtml(item.summary)}</p>
        <p>${escapeHtml(item.requirement)}</p>
        <div class="list-item">
          <header><h5>项目简介</h5><button class="ghost-button" type="button" data-resume="${item.publisherId}">预览发布者简历</button></header>
          <p>${escapeHtml(item.projectSummary || "暂未补充项目简介")}</p>
        </div>
        <div class="list-item">
          <header><h5>发布者</h5><span class="file-meta">${escapeHtml(publisher.campus)} · ${escapeHtml(publisher.college)}</span></header>
          <p>${escapeHtml(privacyLine(publisher, false))}</p>
        </div>
        <div class="list-item">
          <header><h5>指导老师</h5><span class="file-meta">${escapeHtml(item.teacherStatus)}</span></header>
          <p>${escapeHtml(item.teacherName || "未填写")}</p>
        </div>
        ${
          canApply
            ? `<label><span>申请留言</span><textarea id="applicationMessage" rows="4" placeholder="说明你的技能、时间投入和可承担工作"></textarea></label>
               <button class="primary-button" type="button" data-submit-application="${item.id}">提交申请</button>`
            : `<div class="list-item"><h5>${escapeHtml(action.label)}</h5><p>${escapeHtml(action.reason)}</p><p class="file-meta">${escapeHtml(action.next)}</p></div>`
        }
      </div>
    `;
    $("#detailDialog").showModal();
    if (focusApply) $("#applicationMessage")?.focus();
  }

  function openResumePreview(userId) {
    const user = userById(userId);
    const dialog = $("#detailDialog");
    const awards = (user.awards || []).length
      ? user.awards
          .map(
            (award) => `
              <div class="resume-award">
                <strong>${escapeHtml(award.shortName || shortNameForAward(award.name))} ${escapeHtml(awardText(award.award))}</strong>
                <span>${escapeHtml(award.name)} · ${escapeHtml(String(award.year || "未填年份"))} · ${escapeHtml(roleText(award.role, award.solo))}</span>
              </div>
            `,
          )
          .join("")
      : `<p class="file-meta">暂未添加竞赛履历。</p>`;
    $("#detailContent").innerHTML = `
      <div class="dialog-content resume-dialog-content">
        <div class="resume-header">
          <span class="avatar avatar-large">${avatarMarkup(user)}</span>
          <div>
            <span class="eyebrow">个人简历预览</span>
            <h3>${escapeHtml(user.nickname || "未填写昵称")}</h3>
            <p class="file-meta">${escapeHtml(user.grade || "未填写年级")} · ${escapeHtml(user.campus || "未填写校区")} · ${escapeHtml(user.college || "未填写学院")} · ${escapeHtml(user.major || "未填写专业")}</p>
          </div>
        </div>
        <section class="resume-section">
          <h4>能力标签</h4>
          <div class="card-tags">${(user.tags || []).map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("") || `<span class="file-meta">暂未添加能力标签</span>`}</div>
        </section>
        <section class="resume-section">
          <h4>奖项及简称</h4>
          <div class="resume-awards">${awards}</div>
        </section>
        <section class="resume-section">
          <h4>个人简介</h4>
          <p>${escapeHtml(user.bio || "暂未填写个人简介")}</p>
        </section>
        <div class="action-note"><strong>联系方式</strong><span>${escapeHtml(privacyLine(user, false))}</span></div>
      </div>
    `;
    if (!dialog.open) dialog.showModal();
  }

  function submitApplication(recruitmentId) {
    const item = state.recruitments.find((rec) => rec.id === recruitmentId);
    const message = $("#applicationMessage")?.value.trim();
    if (!item || !message) {
      toast("请填写申请留言", "error");
      return;
    }
    item.applications ||= [];
    if (item.applications.some((app) => app.userId === CURRENT_USER_ID)) {
      toast("你已申请过该招募", "error");
      return;
    }
    if (item.status !== "open" || remainingSlots(item) <= 0) {
      toast(item.status !== "open" ? "该招募当前不可申请" : "队伍已满员，无法申请", "error");
      return;
    }
    item.applications.push({
      id: uid("app"),
      userId: CURRENT_USER_ID,
      message,
      status: "pending",
      createdAt: new Date().toISOString(),
    });
    addMessage("notification", "申请已提交", `你已申请加入 ${item.competition}。`);
    saveState();
    renderAll();
    $("#detailDialog").close();
    toast("申请已提交");
  }

  function renderProfile() {
    const user = currentUser();
    $("#awardList").innerHTML = (user.awards || [])
      .map(
        (award) => `
          <div class="award-row">
            <header>
              <h5>${escapeHtml(award.name)}</h5>
              <button class="ghost-button" type="button" data-delete-award="${award.id}">删除</button>
            </header>
            <div class="file-meta">${escapeHtml(award.shortName || shortNameForAward(award.name))} · ${award.year || "未填年份"} · ${awardLevelText(award.level)} · ${roleText(award.role, award.solo)}</div>
            <strong>${escapeHtml(awardText(award.award))}</strong>
          </div>
        `,
      )
      .join("");
    renderAwardPreview();
  }

  function populateProfileForm() {
    const form = $("#profileForm");
    const user = currentUser();
    Object.entries(user).forEach(([key, value]) => {
      const field = form.elements[key];
      if (!field || key === "tags") return;
      field.value = value ?? "";
    });
    setMultiValues(form.elements.tags, user.tags || []);
    setChecklistValues("profileTagChecklist", user.tags || []);
  }

  function renderMine() {
    const mine = state.recruitments.filter((item) => item.publisherId === CURRENT_USER_ID);
    $("#myRecruitments").innerHTML = mine.length
      ? mine.map(myRecruitmentRow).join("")
      : `<div class="list-item"><h5>还没有发布招募</h5></div>`;
    const reviews = mine.flatMap((item) =>
      (item.applications || []).map((app) => ({
        recruitment: item,
        application: app,
        user: userById(app.userId),
      })),
    );
    $("#applicationReview").innerHTML = reviews.length
      ? reviews.map(applicationRow).join("")
      : `<div class="list-item"><h5>暂无申请</h5></div>`;
  }

  function myRecruitmentRow(item) {
    const pending = (item.applications || []).filter((app) => app.status === "pending").length;
    return `
      <article class="list-item">
        <header>
          <h5>${escapeHtml(item.projectTitle || item.competition)}</h5>
          <span class="status-pill ${item.status}">${statusText(item.status)}</span>
        </header>
        <p class="file-meta">${escapeHtml(programById(item.programId).name)} · ${escapeHtml(item.campus)} · ${item.current}/${item.total} 人 · 待审 ${pending} · 截止 ${formatTime(item.deadline)}</p>
        <div class="item-actions">
          <button class="ghost-button" type="button" data-detail="${item.id}">查看详情</button>
          <button class="ghost-button danger" type="button" data-close-recruitment="${item.id}" ${item.status !== "open" ? "disabled" : ""}>关闭招募</button>
        </div>
      </article>
    `;
  }

  function applicationRow({ recruitment, application, user }) {
    const isAccepted = application.status === "accepted";
    const canReview = currentRole() === "captain" && application.status === "pending";
    return `
      <article class="list-item">
        <header>
          <h5>${escapeHtml(user.nickname)} 申请 ${escapeHtml(recruitment.competition)}</h5>
          <span class="status-pill ${application.status === "pending" ? "open" : "closed"}">${applicationStatus(application.status)}</span>
        </header>
        <p class="file-meta">${escapeHtml(user.grade || "未填写年级")} · ${escapeHtml(user.campus)} · ${escapeHtml(user.college)}</p>
        <div class="card-tags">${(user.tags || []).map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}</div>
        <button class="ghost-button" type="button" data-resume="${user.id}">预览简历</button>
        <p>${escapeHtml(application.message)}</p>
        <p class="file-meta">${escapeHtml(privacyLine(user, isAccepted))}</p>
        ${
          canReview
            ? `<div class="item-actions">
                <button class="primary-button" type="button" data-approve-app="${application.id}">通过</button>
                <button class="ghost-button danger" type="button" data-reject-app="${application.id}">拒绝</button>
              </div>`
            : application.status === "pending"
              ? `<div class="action-note"><strong>切换到队长身份后处理</strong><span>申请者身份下不会显示审核操作。</span></div>`
              : ""
        }
      </article>
    `;
  }

  function reviewApplication(applicationId, approve) {
    for (const recruitment of state.recruitments) {
      const app = (recruitment.applications || []).find((item) => item.id === applicationId);
      if (!app) continue;
      if (app.status !== "pending") {
        toast("该申请已经处理过", "error");
        return;
      }
      if (approve && remainingSlots(recruitment) <= 0) {
        toast("队伍已满员，不能继续通过申请", "error");
        return;
      }
      app.status = approve ? "accepted" : "rejected";
      app.reviewedAt = new Date().toISOString();
      const applicant = userById(app.userId);
      if (approve) {
        recruitment.current = Math.min(recruitment.total, recruitment.current + 1);
        addMessage(
          "conversation",
          `${applicant.nickname} · ${recruitment.competition}`,
          `申请已通过，双方可根据隐私设置查看联系方式。`,
          contactCard(applicant, currentUser()),
        );
        addMessage("notification", "申请已通过", `${applicant.nickname} 已加入 ${recruitment.competition}。`);
      } else {
        addMessage("notification", "申请已拒绝", `${applicant.nickname} 的申请已拒绝。`);
      }
      saveState();
      renderAll();
      toast(approve ? "申请已通过" : "申请已拒绝");
      return;
    }
  }

  function renderMessages() {
    const applications = userApplications();
    const pendingApps = applications.filter(({ application }) => application.status === "pending");
    const acceptedApps = applications.filter(({ application }) => application.status === "accepted");
    const rejectedApps = applications.filter(({ application }) => application.status === "rejected");
    const applicationMessages = state.messages.filter((message) => /申请|通过|拒绝/.test(`${message.title}${message.body}`));
    const otherMessages = state.messages.filter((message) => !applicationMessages.includes(message));
    const conversations = [...state.conversations].sort((a, b) => Number(Boolean(b.contact)) - Number(Boolean(a.contact)));
    $("#notificationList").innerHTML =
      applications.length || state.messages.length
        ? `${applicationGroup("待审核", pendingApps)}${applicationGroup("已通过", acceptedApps)}${applicationGroup("已拒绝", rejectedApps)}${messageGroup("系统通知", otherMessages)}`
        : `<div class="list-item"><h5>还没有申请记录</h5><p class="file-meta">从“找队伍”选择一条匹配原因清晰的招募开始。</p></div>`;
    $("#conversationList").innerHTML = conversations.length
      ? `${messageGroup("联系方式卡片", conversations.filter((item) => item.contact), conversationRow)}${messageGroup("站内对话", conversations.filter((item) => !item.contact), conversationRow)}`
      : `<div class="list-item"><h5>暂无站内对话</h5></div>`;
  }

  function applicationGroup(title, items) {
    if (!items.length) return "";
    return `<div class="message-group"><h4>${title}</h4>${items.map(applicationProgressRow).join("")}</div>`;
  }

  function applicationProgressRow({ recruitment, application }) {
    const publisher = userById(recruitment.publisherId);
    const status = applicationStatus(application.status);
    const contactReady = application.status === "accepted";
    return `
      <article class="list-item progress-row">
        <header>
          <h5>${escapeHtml(recruitment.projectTitle || recruitment.competition)}</h5>
          <span class="status-pill ${application.status === "pending" ? "open" : application.status === "accepted" ? "open" : "closed"}">${status}</span>
        </header>
        <p>${escapeHtml(application.message || "未填写留言")}</p>
        <p class="file-meta">${escapeHtml(programById(recruitment.programId).name)} · ${escapeHtml(recruitment.campus)} · 队长 ${escapeHtml(publisher.nickname)} · ${formatTime(application.createdAt)}</p>
        <p class="file-meta">${contactReady ? "已通过后可查看双方隐私设置允许的联系方式。" : application.status === "pending" ? "队长尚未处理，暂不释放联系方式。" : "该申请未通过，联系方式不会释放。"}</p>
      </article>
    `;
  }

  function messageGroup(title, items, renderer = messageRow) {
    if (!items.length) return "";
    return `<div class="message-group"><h4>${title}</h4>${items.map(renderer).join("")}</div>`;
  }

  function messageRow(message) {
    return `
      <article class="list-item">
        <header>
          <h5>${escapeHtml(message.title)}</h5>
          <span class="file-meta">${message.read ? "已读" : "未读"}</span>
        </header>
        <p>${escapeHtml(message.body)}</p>
        <span class="file-meta">${formatTime(message.createdAt)}</span>
      </article>
    `;
  }

  function conversationRow(message) {
    const contact = message.contact || "";
    return `
      <article class="list-item">
        <header>
          <h5>${escapeHtml(message.title)}</h5>
          <span class="file-meta">${formatTime(message.createdAt)}</span>
        </header>
        <p>${escapeHtml(message.body)}</p>
        ${contact ? `<p class="file-meta">${escapeHtml(contact)}</p><button class="ghost-button" type="button" data-copy-contact="${escapeAttr(contact)}">复制联系方式</button>` : ""}
      </article>
    `;
  }

  function renderCollaboration() {
    const matches = collaborationMatches();
    const doneCount = matches.filter((match) => collaborationTasks(match).every((task) => task.done)).length;
    const meetingCount = matches.filter((match) => Boolean(collaborationRecord(match.key).meetingAt)).length;
    $("#collaborationStats").innerHTML = [
      ["已匹配", matches.length],
      ["清单完成", doneCount],
      ["已约同步", meetingCount],
    ]
      .map(([label, value]) => `<div class="collab-stat"><span>${label}</span><strong>${value}</strong></div>`)
      .join("");
    $("#collaborationList").innerHTML = matches.length
      ? matches.map(collaborationCard).join("")
      : `<div class="list-item collab-empty">
          <h5>还没有可协作的匹配</h5>
          <p class="file-meta">申请通过后，联系方式、第一次同步和资料补齐会自动进入这里。</p>
          <button class="primary-button" type="button" data-view-jump="discover" data-step-jump="discover">去找队伍</button>
        </div>`;
    renderCollaborationFiles();
  }

  function collaborationMatches() {
    const matches = [];
    state.recruitments.forEach((recruitment) => {
      (recruitment.applications || [])
        .filter((application) => application.status === "accepted")
        .forEach((application) => {
          if (application.userId === CURRENT_USER_ID && recruitment.publisherId !== CURRENT_USER_ID) {
            matches.push({
              key: collaborationKey(recruitment, application),
              mode: "applicant",
              roleLabel: "申请者视角",
              recruitment,
              application,
              counterpart: userById(recruitment.publisherId),
            });
          }
          if (recruitment.publisherId === CURRENT_USER_ID && application.userId !== CURRENT_USER_ID) {
            matches.push({
              key: collaborationKey(recruitment, application),
              mode: "captain",
              roleLabel: "队长视角",
              recruitment,
              application,
              counterpart: userById(application.userId),
            });
          }
        });
    });
    return matches.sort((a, b) => new Date(b.application.reviewedAt || b.application.createdAt) - new Date(a.application.reviewedAt || a.application.createdAt));
  }

  function collaborationCard(match) {
    const { recruitment, application, counterpart } = match;
    const record = collaborationRecord(match.key);
    const tasks = collaborationTasks(match);
    const done = tasks.filter((task) => task.done).length;
    const nextTask = tasks.find((task) => !task.done);
    const contact = collaborationContact(match);
    const firstMessage = application.message || "未填写申请留言";
    const noteValue = Object.prototype.hasOwnProperty.call(record, "note") ? record.note : firstMessage;
    return `
      <article class="collab-card">
        <header class="collab-card-head">
          <div>
            <span class="eyebrow">${escapeHtml(match.roleLabel)}</span>
            <h4>${escapeHtml(recruitment.projectTitle || recruitment.competition)}</h4>
            <p>${escapeHtml(programById(recruitment.programId).name)} · ${escapeHtml(recruitment.competition || "未指定竞赛")}</p>
          </div>
          <span class="status-pill open">协作中 ${done}/${tasks.length}</span>
        </header>
        <div class="collab-meta">
          <span>对接人：${escapeHtml(counterpart.nickname)}</span>
          <span>${escapeHtml(counterpart.campus)} · ${escapeHtml(counterpart.college)}</span>
          <span>通过时间：${formatTime(application.reviewedAt || application.createdAt)}</span>
        </div>
        <div class="collab-contact">
          <div>
            <strong>联系卡</strong>
            <p>${escapeHtml(contact)}</p>
          </div>
          <button class="ghost-button" type="button" data-copy-collab-contact="${escapeAttr(contact)}">复制联系卡</button>
        </div>
        <div class="collab-next">
          <strong>${nextTask ? `下一步：${nextTask.label}` : "协作清单已完成"}</strong>
          <span>${nextTask ? nextTask.hint : "可以继续补充资料或在备注里记录后续安排。"}</span>
        </div>
        <div class="collab-task-list">
          ${tasks
            .map(
              (task) => `
                <label class="collab-task ${task.done ? "done" : ""}">
                  <input
                    type="checkbox"
                    data-collab-key="${escapeAttr(match.key)}"
                    data-collab-task="${escapeAttr(task.id)}"
                    ${task.done ? "checked" : ""}
                  />
                  <span>
                    <strong>${escapeHtml(task.label)}</strong>
                    <small>${escapeHtml(task.hint)}</small>
                  </span>
                </label>
              `,
            )
            .join("")}
        </div>
        <div class="collab-form-row">
          <label>
            <span>第一次同步时间</span>
            <input type="datetime-local" value="${escapeAttr(toDatetimeLocal(record.meetingAt))}" data-collab-key="${escapeAttr(match.key)}" data-collab-meeting />
          </label>
          <label>
            <span>协作备注</span>
            <textarea rows="3" data-collab-key="${escapeAttr(match.key)}" data-collab-note placeholder="记录分工、会议结论或材料缺口">${escapeHtml(noteValue || "")}</textarea>
          </label>
        </div>
        <div class="item-actions">
          <button class="ghost-button" type="button" data-detail="${recruitment.id}">查看招募详情</button>
          <button class="ghost-button" type="button" data-open-collab-files>打开资料库</button>
        </div>
      </article>
    `;
  }

  function collaborationTasks(match) {
    const record = collaborationRecord(match.key);
    const checked = new Set(record.checked || []);
    const hasMeeting = Boolean(record.meetingAt);
    return [
      {
        id: "contact",
        label: "确认双方联系方式",
        hint: "复制联系卡后在微信、QQ 或线下渠道完成确认。",
        done: checked.has("contact"),
      },
      {
        id: "role",
        label: "明确分工与投入",
        hint: match.mode === "captain" ? "告诉新成员负责范围、周投入和验收物。" : "向队长确认你承担的模块和每周投入。",
        done: checked.has("role"),
      },
      {
        id: "meeting",
        label: "约第一次同步",
        hint: hasMeeting ? `已约 ${formatTime(record.meetingAt)}` : "建议 24 小时内完成第一次同步。",
        done: checked.has("meeting") || hasMeeting,
      },
      {
        id: "materials",
        label: "补齐申报/答辩材料",
        hint: "把需求、分工、附件和截止风险整理到可交付清单。",
        done: checked.has("materials"),
      },
    ];
  }

  function renderCollaborationFiles() {
    const files = state.files.filter((file) => file.scope === "collaboration" || file.scope === "recruitment");
    $("#collaborationFileList").innerHTML = files.length
      ? files
          .slice(0, 5)
          .map(
            (file) => `
              <article class="list-item">
                <header><h5>${escapeHtml(file.name)}</h5><span class="file-meta">${formatBytes(file.size)}</span></header>
                <p class="file-meta">${escapeHtml(scopeText(file.scope))} · ${formatTime(file.createdAt)}</p>
              </article>
            `,
          )
          .join("")
      : `<div class="list-item">
          <h5>暂无协作资料</h5>
          <p class="file-meta">在文件与备份中把附件归档为“协作资料”后会显示在这里。</p>
          <button class="ghost-button" type="button" data-open-collab-files>打开文件与备份</button>
        </div>`;
  }

  function collaborationKey(recruitment, application) {
    return `${recruitment.id}:${application.userId}`;
  }

  function collaborationRecord(key) {
    return state.collaboration?.[key] || { checked: [], note: "", meetingAt: "" };
  }

  function ensureCollaborationRecord(key) {
    state.collaboration ||= {};
    state.collaboration[key] ||= { checked: [], note: "", meetingAt: "" };
    state.collaboration[key].checked ||= [];
    return state.collaboration[key];
  }

  function updateCollaborationTask(key, taskId, checked) {
    const record = ensureCollaborationRecord(key);
    const tasks = new Set(record.checked || []);
    if (checked) tasks.add(taskId);
    else tasks.delete(taskId);
    record.checked = Array.from(tasks);
    record.updatedAt = new Date().toISOString();
    saveState();
    renderCollaboration();
  }

  function updateCollaborationField(key, field, value, persist = true) {
    const record = ensureCollaborationRecord(key);
    record[field] = field === "meetingAt" && value ? new Date(value).toISOString() : value;
    record.updatedAt = new Date().toISOString();
    if (persist) {
      saveState();
      renderCollaboration();
    }
  }

  function collaborationContact(match) {
    const applicant = match.mode === "applicant" ? currentUser() : match.counterpart;
    const publisher = match.mode === "applicant" ? match.counterpart : currentUser();
    return contactCard(applicant, publisher);
  }

  function renderAdmin() {
    $("#adminTags").innerHTML = state.tags
      .map((tag) => `<span class="chip">${escapeHtml(tag.name)} <button type="button" class="ghost-button" data-delete-tag="${tag.id}">删</button></span>`)
      .join("");
    $("#adminCompetitions").innerHTML = state.competitions
      .map(
        (item) => `
          <div class="list-item">
            <header><h5>${escapeHtml(item.name)}</h5><button class="ghost-button" type="button" data-delete-competition="${item.id}">删除</button></header>
            <span class="file-meta">${escapeHtml(item.level)}级</span>
          </div>
        `,
      )
      .join("");
    $("#adminProjects").innerHTML = (state.projects || []).filter((project) => project.active !== false).length
      ? (state.projects || [])
          .filter((project) => project.active !== false)
          .map(
            (project) => `
              <div class="list-item">
                <header><h5>${escapeHtml(project.title)}</h5><button class="ghost-button danger" type="button" data-delete-project="${project.id}">停用</button></header>
                <span class="file-meta">${escapeHtml(programById(project.programId).name)} · ${escapeHtml(project.source === "library" ? "项目库" : "自定义")}</span>
              </div>
            `,
          )
          .join("")
      : `<div class="list-item"><h5>项目库为空</h5></div>`;
    const rolePanel = $("#adminRolePanel");
    if (rolePanel) rolePanel.classList.toggle("hidden", !canManageAdmins(currentRole()));
    if (canManageAdmins(currentRole())) {
      $("#adminUsers").innerHTML = state.users
        .filter((user) => user.id !== state.platform.creatorId)
        .map(
          (user) => `
            <div class="list-item role-user-row">
              <div>
                <h5>${escapeHtml(user.nickname)}</h5>
                <span class="file-meta">${escapeHtml(user.college || "未填写学院")} · ${user.systemRole === "admin" ? "系统管理员" : "普通成员"}</span>
              </div>
              ${user.systemRole === "admin" ? `<button class="ghost-button danger" type="button" data-revoke-admin="${user.id}">撤销管理员</button>` : `<button class="ghost-button" type="button" data-appoint-admin="${user.id}">任命管理员</button>`}
            </div>
          `,
        )
        .join("");
      const logs = state.platform.auditLog || [];
      $("#adminAuditLog").innerHTML = logs.length
        ? `<h5>最近操作</h5>${logs.slice(0, 5).map((log) => `<div class="file-meta">${log.action === "appoint_admin" ? "任命管理员" : "撤销管理员"} · ${escapeHtml(userById(log.targetId).nickname)} · ${formatTime(log.createdAt)}</div>`).join("")}`
        : `<p class="file-meta">暂无任免记录</p>`;
    } else {
      $("#adminUsers").innerHTML = `<div class="list-item"><h5>权限受限</h5><p class="file-meta">切换到平台创建者身份后管理系统管理员。</p></div>`;
      $("#adminAuditLog").innerHTML = "";
    }
    const pendingCustom = state.customTags.filter((tag) => tag.status === "pending");
    $("#customTagReview").innerHTML = pendingCustom.length
      ? pendingCustom
          .map(
            (tag) => `
            <div class="list-item">
              <header><h5>${escapeHtml(tag.name)}</h5><span class="file-meta">${escapeHtml(tag.requester)}</span></header>
              <div class="item-actions">
                <button class="primary-button" type="button" data-approve-tag="${tag.id}">通过</button>
                <button class="ghost-button danger" type="button" data-reject-tag="${tag.id}">拒绝</button>
              </div>
            </div>
          `,
          )
          .join("")
      : `<div class="list-item"><h5>暂无待审标签</h5></div>`;
    const open = state.recruitments.filter((item) => item.status === "open").length;
    const accepted = state.recruitments.flatMap((item) => item.applications || []).filter((app) => app.status === "accepted").length;
    const pendingApps = state.recruitments.flatMap((item) => item.applications || []).filter((app) => app.status === "pending").length;
    const reports = state.reports.filter((item) => item.status === "pending").length;
    $("#adminStats").innerHTML = [
      ["开放招募", open],
      ["成功匹配", accepted],
      ["待审申请", pendingApps],
      ["待处理举报", reports],
    ]
      .map(([label, value]) => `<div class="stat-box"><span>${label}</span><strong>${value}</strong></div>`)
      .join("");
    $("#reportList").innerHTML = state.reports.length
      ? state.reports
          .map(
            (report) => `
          <div class="list-item">
            <header><h5>${escapeHtml(report.title)}</h5><span class="file-meta">${report.status === "resolved" ? "已处理" : "待处理"}</span></header>
            <p>${escapeHtml(report.body)}</p>
            ${report.status !== "resolved" ? `<button class="ghost-button" type="button" data-resolve-report="${report.id}">标记处理</button>` : ""}
          </div>
        `,
          )
          .join("")
      : `<div class="list-item"><h5>暂无举报</h5></div>`;
  }

  function renderFiles() {
    $("#fileLibrary").innerHTML = state.files.length
      ? state.files
          .map(
            (file) => `
          <article class="file-row">
            <div>
              <h5>${escapeHtml(file.name)}</h5>
              <div class="file-meta">${escapeHtml(scopeText(file.scope))} · ${escapeHtml(file.type || "unknown")} · ${formatBytes(file.size)} · ${formatTime(file.createdAt)}</div>
            </div>
            <div class="item-actions">
              <button class="ghost-button" type="button" data-download-file="${file.id}" ${file.dataUrl ? "" : "disabled"}>下载</button>
              <button class="ghost-button danger" type="button" data-delete-file="${file.id}">删除</button>
            </div>
          </article>
        `,
          )
          .join("")
      : `<div class="list-item"><h5>本地文件库为空</h5><p class="file-meta">上传头像、招募附件或在文件管理页入库后会显示在这里。</p></div>`;
  }

  function addMessage(kind, title, body, contact = "") {
    const target = kind === "conversation" ? state.conversations : state.messages;
    target.unshift({
      id: uid(kind === "conversation" ? "conv" : "m"),
      kind,
      title,
      body,
      contact,
      read: false,
      createdAt: new Date().toISOString(),
    });
  }

  function exportData() {
    downloadJson(state, `hiteam-backup-${safeDate()}.json`);
    toast("备份已生成");
  }

  function importData(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result));
        const summary = validateImportPayload(parsed);
        $("#importPreview").innerHTML = importSummaryMarkup(summary);
        if (!summary.valid) {
          toast(summary.reason, "error");
          return;
        }
        if (!confirm(`导入 ${summary.recruitments} 条招募、${summary.drafts} 个草稿、${summary.users} 个用户，继续吗？`)) return;
        state = ensureStateShape(parsed);
        saveState();
        renderAll();
        toast("JSON 已导入");
      } catch {
        $("#importPreview").innerHTML = `<div class="list-item"><h5>导入失败</h5><p class="file-meta">JSON 无法解析</p></div>`;
        toast("导入失败，JSON 无法解析", "error");
      } finally {
        event.target.value = "";
      }
    };
    reader.readAsText(file, "utf-8");
  }

  function validateImportPayload(payload) {
    if (!payload || typeof payload !== "object") return { valid: false, reason: "导入失败，JSON 不是对象" };
    if (!Array.isArray(payload.recruitments)) return { valid: false, reason: "导入失败，缺少 recruitments 数组" };
    if (!Array.isArray(payload.users)) return { valid: false, reason: "导入失败，缺少 users 数组" };
    return {
      valid: true,
      reason: "",
      version: payload.version || "未知版本",
      recruitments: payload.recruitments.length,
      drafts: Array.isArray(payload.drafts) ? payload.drafts.length : 0,
      users: payload.users.length,
      files: Array.isArray(payload.files) ? payload.files.length : 0,
    };
  }

  function importSummaryMarkup(summary) {
    if (!summary.valid) {
      return `<div class="list-item"><h5>导入校验失败</h5><p class="file-meta">${escapeHtml(summary.reason)}</p></div>`;
    }
    return `
      <div class="list-item">
        <h5>导入校验通过</h5>
        <p class="file-meta">版本 ${escapeHtml(summary.version)} · 招募 ${summary.recruitments} · 草稿 ${summary.drafts} · 用户 ${summary.users} · 文件 ${summary.files}</p>
      </div>
    `;
  }

  async function readFiles(files, scope) {
    const list = Array.from(files || []);
    const records = [];
    for (const file of list) {
      const dataUrl = file.size <= 350 * 1024 ? await readSingleFileAsDataUrl(file) : "";
      records.push(fileRecord(file, scope, dataUrl));
    }
    return records;
  }

  function fileRecord(file, scope, dataUrl = "") {
    return {
      id: uid("file"),
      name: file.name,
      type: file.type,
      size: file.size,
      scope,
      dataUrl,
      createdAt: new Date().toISOString(),
    };
  }

  function readSingleFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function downloadJson(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function downloadDataUrl(file) {
    const link = document.createElement("a");
    link.href = file.dataUrl;
    link.download = file.name;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function currentUser() {
    return state.users.find((user) => user.id === CURRENT_USER_ID) || state.users[0];
  }

  function userById(id) {
    return state.users.find((user) => user.id === id) || currentUser();
  }

  function privacyLine(user, matched) {
    const realName = canReveal(user.realNameVisibility, matched) ? user.realName || "未填姓名" : "姓名隐藏";
    const contact = canReveal(user.contactVisibility, matched) ? user.contact || "未填联系方式" : "联系方式隐藏";
    return `${realName} · ${contact}`;
  }

  function canReveal(mode, matched) {
    if (mode === "public") return true;
    if (mode === "matched") return matched;
    return false;
  }

  function contactCard(applicant, publisher) {
    return `${applicant.nickname}: ${privacyLine(applicant, true)} | ${publisher.nickname}: ${privacyLine(publisher, true)}`;
  }

  function avatarMarkup(user) {
    if (user.avatar) return `<img src="${escapeAttr(user.avatar)}" alt="${escapeAttr(user.nickname)}" />`;
    return escapeHtml((user.nickname || "H").slice(0, 1));
  }

  function statusText(status) {
    return { open: "招募中", closed: "已关闭", expired: "已截止" }[status] || status;
  }

  function statusWeight(status) {
    return { open: 0, closed: 1, expired: 2 }[status] ?? 3;
  }

  function applicationStatus(status) {
    return { pending: "待审核", accepted: "已通过", rejected: "已拒绝" }[status] || status;
  }

  function awardLevelText(level) {
    return { national: "国家级", provincial: "省级", school: "校级" }[level] || level;
  }

  function roleText(role, solo = false) {
    if (solo) return "单人参赛";
    return { captain: "队长/第一负责人", second: "第2-3核心成员", member: "第4名及以后普通队员" }[role] || role;
  }

  function awardText(award) {
    return { special: "特等奖", first: "一等奖", second: "二等奖", third: "三等奖", excellent: "优秀奖/参与奖" }[award] || award;
  }

  function getMultiValues(select) {
    return Array.from(select?.selectedOptions || []).map((option) => option.value);
  }

  function setMultiValues(select, values) {
    if (!select) return;
    const wanted = new Set(values || []);
    Array.from(select.options).forEach((option) => {
      option.selected = wanted.has(option.value);
    });
  }

  function getChecklistValues(containerId) {
    return $$(`#${containerId} input[type="checkbox"]:checked`).map((input) => input.value);
  }

  function setChecklistValues(containerId, values) {
    const wanted = new Set(values || []);
    $$(`#${containerId} input[type="checkbox"]`).forEach((input) => {
      input.checked = wanted.has(input.value);
    });
    const selectId = containerId === "publishTagChecklist" ? "publishTagSelect" : "profileTagSelect";
    setMultiValues($(`#${selectId}`), values || []);
  }

  function clearChecklist(containerId) {
    $$(`#${containerId} input[type="checkbox"]`).forEach((input) => {
      input.checked = false;
    });
    const selectId = containerId === "publishTagChecklist" ? "publishTagSelect" : "profileTagSelect";
    setMultiValues($(`#${selectId}`), []);
  }

  function overlap(a = [], b = []) {
    const set = new Set(a);
    return b.filter((item) => set.has(item)).length;
  }

  function normalizeSearchText(value = "") {
    return String(value).trim().toLowerCase().replace(/\s+/g, "");
  }

  function remainingSlots(recruitment) {
    return Math.max(0, Number(recruitment.total || 0) - Number(recruitment.current || 0));
  }

  function hasApplied(recruitment, userId) {
    return (recruitment.applications || []).some((app) => app.userId === userId && app.status !== "rejected");
  }

  function round1(value) {
    return Math.round(value * 10) / 10;
  }

  function uid(prefix) {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }

  function safeDate() {
    return new Date().toISOString().slice(0, 10);
  }

  function formatTime(value) {
    if (!value) return "未设置";
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return "未设置";
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function toDatetimeLocal(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const offset = date.getTimezoneOffset();
    const local = new Date(date.getTime() - offset * 60000);
    return local.toISOString().slice(0, 16);
  }

  function scopeText(scope) {
    return { profile: "个人档案", recruitment: "招募材料", collaboration: "协作资料", admin: "管理资料" }[scope] || scope;
  }

  function formatBytes(size) {
    if (!size) return "0 B";
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }

  function toast(message, type = "ok") {
    const node = document.createElement("div");
    node.className = `toast ${type === "error" ? "error" : ""}`;
    node.textContent = message;
    while ($("#toastArea").children.length >= 3) {
      $("#toastArea").firstElementChild?.remove();
    }
    $("#toastArea").append(node);
    setTimeout(() => node.remove(), 3600);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replaceAll("`", "&#096;");
  }
})();
