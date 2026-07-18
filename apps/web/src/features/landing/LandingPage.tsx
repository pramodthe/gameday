import {
  Activity,
  ArrowDown,
  ArrowRight,
  BrainCircuit,
  Camera,
  Check,
  ChevronRight,
  CircleGauge,
  Dumbbell,
  Eye,
  Flame,
  Footprints,
  LockKeyhole,
  Mic2,
  MoonStar,
  Play,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Utensils,
  Volume2,
} from 'lucide-react';
import { motion } from 'motion/react';
import './landing.css';

type LandingPageProps = {
  onLaunch: () => void;
};

const readinessSignals = [
  { icon: MoonStar, label: 'Sleep', value: '5.0h', detail: 'Below baseline', tone: 'warn' },
  { icon: CircleGauge, label: 'Recovery', value: '42%', detail: 'Adjust today', tone: 'warn' },
  { icon: Dumbbell, label: 'Training', value: '6 PM', detail: 'Team practice', tone: 'good' },
  { icon: Utensils, label: 'Fuel', value: 'Low', detail: 'Meal needed', tone: 'risk' },
];

const steps = [
  {
    number: '01',
    icon: Mic2,
    title: 'Tell it how you feel.',
    body: 'Nova asks four focused questions about sleep, recovery, training, fuel, and mindset. You answer naturally.',
    note: '90-second voice check-in',
  },
  {
    number: '02',
    icon: ScanLine,
    title: 'Move. Get seen.',
    body: 'Camera-guided movement checks count reps, measure position, and turn your form into useful coaching context.',
    note: 'On-device pose tracking',
  },
  {
    number: '03',
    icon: BrainCircuit,
    title: 'Train for today.',
    body: 'Your readiness, movement, and recent history become a practical plan—push, maintain, or recover with a reason.',
    note: 'Personalized daily plan',
  },
];

const proofPoints = [
  ['04', 'daily signals connected'],
  ['90s', 'from check-in to plan'],
  ['01', 'clear decision for today'],
];

function Brand() {
  return (
    <span className="landing-brand" aria-label="GameDay Mirror">
      <span className="landing-brand__mark"><Activity size={18} /></span>
      <span><strong>GAMEDAY</strong><small>mirror</small></span>
    </span>
  );
}

function MirrorPreview() {
  return (
    <div className="landing-preview" aria-label="Preview of the GameDay Mirror readiness check-in">
      <div className="landing-preview__chrome">
        <span><i /> LIVE MIRROR</span>
        <span>07:42 AM</span>
      </div>

      <div className="landing-preview__scene">
        <div className="landing-preview__glow" />
        <div className="landing-athlete" aria-hidden="true">
          <span className="landing-athlete__head" />
          <span className="landing-athlete__body" />
          <span className="landing-athlete__shoulder landing-athlete__shoulder--left" />
          <span className="landing-athlete__shoulder landing-athlete__shoulder--right" />
          <span className="landing-athlete__line landing-athlete__line--one" />
          <span className="landing-athlete__line landing-athlete__line--two" />
          <span className="landing-athlete__joint landing-athlete__joint--one" />
          <span className="landing-athlete__joint landing-athlete__joint--two" />
          <span className="landing-athlete__joint landing-athlete__joint--three" />
        </div>
        <div className="landing-preview__scan" />

        <div className="landing-preview__readiness">
          <span className="landing-micro-label"><CircleGauge size={12} /> BODY TODAY</span>
          {readinessSignals.map(({ icon: Icon, label, value, detail, tone }) => (
            <div className="landing-signal" data-tone={tone} key={label}>
              <span><Icon size={13} /></span>
              <div><strong>{label}</strong><small>{detail}</small></div>
              <b>{value}</b>
            </div>
          ))}
        </div>

        <div className="landing-preview__coach">
          <span className="landing-micro-label"><Sparkles size={12} /> NOVA · LISTENING</span>
          <p>“Five hours logged. That makes two short nights in a row.”</p>
          <div className="landing-wave" aria-hidden="true">
            {Array.from({ length: 18 }, (_, index) => <i key={index} />)}
          </div>
        </div>

        <div className="landing-preview__score">
          <span>READINESS</span>
          <strong>42</strong>
          <small>RECOVERY DAY</small>
        </div>
      </div>

      <div className="landing-preview__footer">
        <span><Camera size={13} /> Camera on</span>
        <span><ShieldCheck size={13} /> Private session</span>
        <span><Volume2 size={13} /> Nova</span>
      </div>
    </div>
  );
}

export function LandingPage({ onLaunch }: LandingPageProps) {
  return (
    <main className="landing-shell">
      <header className="landing-nav">
        <a href="#top" className="landing-nav__brand"><Brand /></a>
        <nav aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#intelligence">The mirror</a>
          <a href="#privacy">Privacy</a>
        </nav>
        <button type="button" className="landing-nav__launch" onClick={onLaunch}>
          Open mirror <ArrowRight size={15} />
        </button>
      </header>

      <section className="landing-hero" id="top">
        <div className="landing-hero__grid" aria-hidden="true" />
        <motion.div
          className="landing-hero__copy"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="landing-kicker"><span>AI PERFORMANCE COACH</span><i /> BUILT FOR REAL TRAINING DAYS</div>
          <h1>Don’t just<br />show up.<br /><em>Show up ready.</em></h1>
          <p>
            A 90-second conversation that turns how you <strong>feel</strong>, how you <strong>move</strong>,
            and what you did <strong>yesterday</strong> into the right plan for today.
          </p>
          <div className="landing-hero__actions">
            <button type="button" className="landing-primary" onClick={onLaunch}>
              Start your check-in <ArrowRight size={18} />
            </button>
            <a href="#how-it-works" className="landing-secondary">
              <span><Play size={13} fill="currentColor" /></span> See how it works
            </a>
          </div>
          <div className="landing-trust">
            <span><Check size={13} /> No wearable required</span>
            <span><Check size={13} /> Camera-first</span>
            <span><Check size={13} /> Free demo</span>
          </div>
        </motion.div>

        <motion.div
          className="landing-hero__visual"
          initial={{ opacity: 0, x: 34, rotate: 1.5 }}
          animate={{ opacity: 1, x: 0, rotate: 0 }}
          transition={{ duration: 0.9, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="landing-hero__stamp"><Eye size={17} /><span>SEE.<br />LISTEN.<br />REMEMBER.</span></div>
          <MirrorPreview />
          <span className="landing-hero__caption">YOUR BODY // YOUR CONTEXT // YOUR CALL</span>
        </motion.div>

        <a className="landing-scroll" href="#problem" aria-label="Scroll to learn more">
          <span>SCROLL TO READ</span><ArrowDown size={15} />
        </a>
      </section>

      <section className="landing-proof" aria-label="Product highlights">
        {proofPoints.map(([value, label]) => (
          <div key={label}><strong>{value}</strong><span>{label}</span></div>
        ))}
        <div className="landing-proof__quote">
          <Activity size={21} />
          <span>Less dashboard.<br /><strong>More direction.</strong></span>
        </div>
      </section>

      <section className="landing-problem" id="problem">
        <div className="landing-section-label"><span>01</span> THE PROBLEM</div>
        <div className="landing-problem__headline">
          <h2>Your body changes daily.<br /><em>Your plan should too.</em></h2>
          <p>Sleep lives in one app. Training in another. Soreness, stress, and fuel usually live nowhere. GameDay Mirror connects the signals that actually shape today’s performance.</p>
        </div>
        <div className="landing-context-line" aria-hidden="true">
          <span>SLEEP</span><i /><span>FUEL</span><i /><span>MOVEMENT</span><i /><span>MEMORY</span><i /><b>YOUR PLAN</b>
        </div>
      </section>

      <section className="landing-how" id="how-it-works">
        <div className="landing-how__intro">
          <div className="landing-section-label landing-section-label--light"><span>02</span> HOW IT WORKS</div>
          <h2>Three moves.<br />One better decision.</h2>
          <p>No charts to decode. No forms to maintain. Just a quick ritual before the work begins.</p>
        </div>
        <div className="landing-steps">
          {steps.map(({ number, icon: Icon, title, body, note }, index) => (
            <article className="landing-step" key={number}>
              <span className="landing-step__number">{number}</span>
              <div className="landing-step__icon"><Icon size={27} /></div>
              <h3>{title}</h3>
              <p>{body}</p>
              <span className="landing-step__note"><Check size={13} /> {note}</span>
              {index < steps.length - 1 && <ArrowRight className="landing-step__arrow" size={22} />}
            </article>
          ))}
        </div>
      </section>

      <section className="landing-intelligence" id="intelligence">
        <div className="landing-intelligence__copy">
          <div className="landing-section-label"><span>03</span> THE INTELLIGENCE</div>
          <h2>A coach that<br /><em>keeps context.</em></h2>
          <p>GameDay Mirror doesn’t hand you a mystery score. It shows what changed, remembers what matters, and explains what to do next.</p>
          <ul>
            <li><BrainCircuit size={18} /><span><strong>Remembers patterns</strong>Connects today’s check-in to recent sessions.</span></li>
            <li><Footprints size={18} /><span><strong>Understands movement</strong>Uses verified reps and form cues—not guesses.</span></li>
            <li><Flame size={18} /><span><strong>Adapts the work</strong>Builds a session around today’s actual capacity.</span></li>
          </ul>
        </div>
        <div className="landing-plan-card">
          <div className="landing-plan-card__top">
            <span><Sparkles size={13} /> TODAY’S GAME PLAN</span>
            <small>JUL 17 · 07:44</small>
          </div>
          <div className="landing-plan-card__readiness">
            <div><strong>42</strong><span>READINESS</span></div>
            <p><b>Recovery day</b>Protect evening practice after a second short-sleep night.</p>
          </div>
          <ol>
            <li><span>01</span><div><small>BEFORE NOON</small><strong>Refuel on purpose</strong><p>Balanced meal + one full bottle of water.</p></div></li>
            <li><span>02</span><div><small>BEFORE PRACTICE</small><strong>Protect the evening session</strong><p>20-minute reset. Skip extra training volume.</p></div></li>
            <li><span>03</span><div><small>12 MINUTES</small><strong>Recovery reset</strong><p>Glute bridge · plank · reverse lunge</p></div></li>
          </ol>
          <div className="landing-plan-card__memory"><BrainCircuit size={15} /><span><strong>Memory shaped this plan</strong>Yesterday: 4.5h sleep + intense session</span></div>
        </div>
      </section>

      <section className="landing-privacy" id="privacy">
        <div className="landing-privacy__mark"><LockKeyhole size={33} /></div>
        <div>
          <div className="landing-section-label landing-section-label--light"><span>04</span> PRIVATE BY DESIGN</div>
          <h2>Your reflection<br />belongs to you.</h2>
        </div>
        <div className="landing-privacy__copy">
          <p>Camera access is used for your live mirror and movement analysis. Raw video is not stored by default, and GameDay Mirror never diagnoses injuries or medical conditions.</p>
          <div>
            <span><ShieldCheck size={15} /> No facial emotion or identity detection</span>
            <span><Camera size={15} /> Camera and microphone controls stay visible</span>
            <span><LockKeyhole size={15} /> Coaching support—not medical advice</span>
          </div>
        </div>
      </section>

      <section className="landing-final">
        <div className="landing-final__rings" aria-hidden="true"><i /><i /><i /></div>
        <span className="landing-final__eyebrow">TODAY ALREADY STARTED</span>
        <h2>Know what your<br />next rep needs.</h2>
        <p>Take 90 seconds. Check your readiness. Move with purpose.</p>
        <button type="button" onClick={onLaunch}>
          Open GameDay Mirror <span><ArrowRight size={19} /></span>
        </button>
      </section>

      <footer className="landing-footer">
        <Brand />
        <p>AI-powered readiness coaching for athletes.</p>
        <div><span>© 2026 GAMEDAY MIRROR</span><a href="#privacy">PRIVACY</a><button type="button" onClick={onLaunch}>LAUNCH APP <ChevronRight size={12} /></button></div>
      </footer>
    </main>
  );
}
