import { useEffect, useRef, useState } from 'react'
import { Button, Typography } from 'antd'
import { ArrowRightOutlined, CheckCircleFilled } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

/** 滚动触发渐入 Hook */
function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold: 0.18, rootMargin: '0px 0px -40px 0px' }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return { ref, visible }
}

/** 单个数据指标 */
function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <div className="landing-stat-item">
      <Typography.Text className="landing-stat-value">{value}</Typography.Text>
      <Typography.Text className="landing-stat-label">{label}</Typography.Text>
    </div>
  )
}

/** 功能区块 — 统一处理渐入动画 */
function FeatureBlock(props: {
  kicker: string
  title: string
  body: string
  points: string[]
  imgSrc: string
  imgAlt: string
  imageLeft?: boolean
  altBg?: boolean
}) {
  const { ref, visible } = useReveal<HTMLDivElement>()

  const visual = (
    <div className="landing-feature-visual">
      <div className="landing-screen-frame">
        <img src={props.imgSrc} alt={props.imgAlt} />
      </div>
    </div>
  )

  const copy = (
    <div className="landing-feature-copy">
      <Typography.Text className="landing-feature-kicker">{props.kicker}</Typography.Text>
      <Typography.Title level={2} className="landing-feature-title">
        {props.title}
      </Typography.Title>
      <Typography.Paragraph className="landing-feature-body">{props.body}</Typography.Paragraph>
      <div className="landing-feature-points">
        {props.points.map((p) => <span key={p}>{p}</span>)}
      </div>
    </div>
  )

  return (
    <section className={`landing-feature ${props.altBg ? 'landing-feature-alt' : ''}`}>
      <div ref={ref} className={`landing-feature-inner ${visible ? 'is-revealed' : ''}`}>
        {props.imageLeft ? visual : copy}
        {props.imageLeft ? copy : visual}
      </div>
    </section>
  )
}

/** 产品介绍页 —— Apple 风格，精致有质感。 */
export function WelcomeGate() {
  const navigate = useNavigate()
  const [scrolled, setScrolled] = useState(false)
  const { ref: heroRef, visible: heroVisible } = useReveal<HTMLDivElement>()
  const { ref: statsRef, visible: statsVisible } = useReveal<HTMLDivElement>()
  const { ref: ctaRef, visible: ctaVisible } = useReveal<HTMLDivElement>()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="landing-root" id="landing-root">
      {/* ── 背景装饰 ── */}
      <div className="landing-bg-decor" aria-hidden="true">
        <div className="landing-orb landing-orb-a" />
        <div className="landing-orb landing-orb-b" />
        <div className="landing-orb landing-orb-c" />
        <div className="landing-orb landing-orb-d" />
      </div>

      {/* ── 顶部导航 ── */}
      <header className={`landing-nav ${scrolled ? 'is-scrolled' : ''}`}>
        <div className="landing-nav-inner">
          <span className="landing-nav-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <span className="landing-nav-dot" />
            AI Interview
          </span>
          <div className="landing-nav-actions">
            <Button className="landing-btn-text" onClick={() => navigate('/login')}>登录</Button>
            <Button className="landing-btn-primary-sm" onClick={() => navigate('/register')}>注册</Button>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="landing-hero">
        <div ref={heroRef} className={`landing-hero-grid ${heroVisible ? 'is-revealed' : ''}`}>
          <div className="landing-hero-copy">
            <Typography.Text className="landing-hero-kicker">AI 模拟面试系统</Typography.Text>
            <Typography.Title level={1} className="landing-hero-title">
              每一次练习，<br />都更接近 offer。
            </Typography.Title>
            <Typography.Paragraph className="landing-hero-body">
              从岗位匹配、简历联动到实时 AI 追问和深度复盘报告，把面试训练集中在一个清爽的工作区里。
            </Typography.Paragraph>
            <div className="landing-hero-cta-row">
              <Button className="landing-btn-primary-lg" onClick={() => navigate('/register')}>
                免费开始使用 <ArrowRightOutlined />
              </Button>
              <Button className="landing-btn-ghost-lg" onClick={() => navigate('/login')}>
                已有账号？登录
              </Button>
            </div>
            <div className="landing-hero-badges">
              <span><CheckCircleFilled /></span>
              <span>智能追问</span>
              <span className="landing-hero-badge-divider" />
              <span>简历联动</span>
              <span className="landing-hero-badge-divider" />
              <span>复盘报告</span>
            </div>
          </div>
          <div className="landing-hero-visual">
            <div className="landing-hero-img-frame">
              <img src="/screenshots/hero-banner.png" alt="AI Interview 系统概览" className="landing-hero-img" />
            </div>
          </div>
        </div>
      </section>

      {/* ── 数据指标 ── */}
      <section className="landing-stats">
        <div ref={statsRef} className={`landing-stats-inner ${statsVisible ? 'is-revealed' : ''}`}>
          <StatItem value="6+" label="覆盖岗位方向" />
          <StatItem value="500+" label="面试题库" />
          <StatItem value="实时" label="AI 智能追问" />
          <StatItem value="多维" label="深度复盘报告" />
        </div>
      </section>

      {/* ── 功能区块 ── */}
      <FeatureBlock
        kicker="首页概览"
        title="一目了然的面试训练看板"
        body="关键指标、最近面试记录、系统健康状态和日历视图一览无余。打开首页就知道今天该练什么、进度如何。"
        points={['综合得分追踪', '面试记录卡片', '系统状态监控']}
        imgSrc="/screenshots/dashboard.png"
        imgAlt="首页概览看板"
        imageLeft
      />

      <FeatureBlock
        kicker="AI 面试"
        title="沉浸式实时模拟面试体验"
        body="选择岗位、上传简历后即刻开始。AI 面试官会根据你的回答智能追问，真实还原面试压力场景，帮助你发现表达弱项并持续提升。"
        points={['岗位定制题库', '简历深度联动', '实时智能追问']}
        imgSrc="/screenshots/landing-interview.png"
        imgAlt="AI 模拟面试界面"
        altBg
      />

      <FeatureBlock
        kicker="题库练习"
        title="海量真题，分岗位定向训练"
        body="覆盖前端、后端、产品、测试等多个方向，支持按岗位、难度和题型筛选。随时开练、反复打磨，每次练习都有详细反馈。"
        points={['多岗位覆盖', '难度分级', '即时反馈']}
        imgSrc="/screenshots/practice.png"
        imgAlt="题库练习界面"
        imageLeft
      />

      <FeatureBlock
        kicker="编程练习"
        title="在线编码，实时运行验证"
        body="内置代码编辑器支持多语言语法高亮和实时运行。写代码、调试、提交一气呵成，面试手写算法不再紧张。"
        points={['在线编辑器', '多语言支持', '实时运行']}
        imgSrc="/screenshots/coding.png"
        imgAlt="编程练习界面"
        altBg
      />

      <FeatureBlock
        kicker="记录与报告"
        title="每次面试都有深度复盘"
        body="完整保留每一次面试过程，支持回放查看。AI 生成的详细分析报告涵盖表达能力、技术深度、项目经验等多维度评估。"
        points={['面试回放', '多维评分', '成长轨迹']}
        imgSrc="/screenshots/landing-report.png"
        imgAlt="面试记录界面"
        imageLeft
      />

      {/* ── CTA ── */}
      <section className="landing-cta">
        <div ref={ctaRef} className={`landing-cta-inner ${ctaVisible ? 'is-revealed' : ''}`}>
          <Typography.Text className="landing-cta-kicker">现在就开始</Typography.Text>
          <Typography.Title level={2} className="landing-cta-title">
            准备好提升面试能力了吗？
          </Typography.Title>
          <Typography.Paragraph className="landing-cta-body">
            注册即享完整功能，从今天开始系统化训练你的面试技巧。
          </Typography.Paragraph>
          <Button className="landing-btn-primary-lg" onClick={() => navigate('/register')}>
            免费注册 <ArrowRightOutlined />
          </Button>
        </div>
      </section>

      {/* ── 底部 ── */}
      <footer className="landing-footer">
        <Typography.Text type="secondary">AI Interview · 模拟面试训练平台</Typography.Text>
      </footer>
    </div>
  )
}
