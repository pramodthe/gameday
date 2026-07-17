import type { DemoQuestion, MirrorMetric, PlanAction } from './types';

export const INITIAL_METRICS: MirrorMetric[] = [
  { key: 'sleep', label: 'Sleep', value: '— hrs', detail: 'Waiting for check-in', tone: 'neutral' },
  { key: 'recovery', label: 'Recovery', value: '—', detail: 'No signal yet', tone: 'neutral' },
  { key: 'training', label: 'Training', value: '—', detail: 'Today’s load', tone: 'neutral' },
  { key: 'fuel', label: 'Fuel', value: '—', detail: 'Nutrition check', tone: 'neutral' },
  { key: 'mindset', label: 'Mindset', value: '—', detail: 'Focus signal', tone: 'neutral' },
  { key: 'spending', label: 'Spending', value: '$—', detail: 'Daily target · $15', tone: 'neutral' },
];

export const DEMO_QUESTIONS: DemoQuestion[] = [
  {
    id: 'sleep',
    prompt: 'How many hours did you sleep, and how recovered do you feel?',
    demoAnswer: 'About five hours. I am pretty tired.',
    acknowledgement: 'Five hours logged. That makes two short nights in a row.',
    updates: {
      sleep: { value: '5 hrs', detail: '2.5 hrs below target', tone: 'attention' },
      recovery: { value: '42%', detail: 'Recovery needs attention', tone: 'attention' },
    },
  },
  {
    id: 'training',
    prompt: 'What training have you completed or planned today?',
    demoAnswer: 'No training yet. We have hard team practice at six.',
    acknowledgement: 'Team practice at six. I have marked the planned load as high.',
    updates: { training: { value: '6 PM', detail: 'Team practice · high load', tone: 'good' } },
  },
  {
    id: 'fuel',
    prompt: 'How has your nutrition been so far today?',
    demoAnswer: 'Mostly good, but I skipped breakfast.',
    acknowledgement: 'Breakfast missed. Fuel becomes the first action before practice.',
    updates: { fuel: { value: 'Missed', detail: 'Breakfast needs recovery', tone: 'risk' } },
  },
  {
    id: 'spending',
    prompt: 'What needs the most discipline today: confidence, focus, or spending?',
    demoAnswer: 'Spending. I ate out again yesterday.',
    acknowledgement: 'Spending noted. I am combining that with yesterday’s dining pattern.',
    updates: {
      mindset: { value: 'Focused', detail: 'Clear accountability target', tone: 'good' },
      spending: { value: '$35', detail: '$20 above daily target', tone: 'risk' },
    },
  },
];

export const DAILY_PLAN: PlanAction[] = [
  { id: 'fuel', eyebrow: 'Before noon', title: 'Refuel on purpose', detail: 'Eat one balanced meal and finish a full bottle of water before the afternoon.' },
  { id: 'recover', eyebrow: 'Before practice', title: 'Protect the evening session', detail: 'Take a 20-minute recovery reset instead of adding extra training volume.' },
  { id: 'spend', eyebrow: 'Off field', title: 'Hold the $15 line', detail: 'Use the meal already available and keep dining spend under today’s target.' },
];

export const MEMORY_TEXT =
  'Yesterday you planned another intense session after only 4.5 hours of sleep. Today’s plan reduces extra load instead of repeating it.';
