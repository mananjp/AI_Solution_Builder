export const en = {
  common: {
    appName: 'SUTRA OS',
    search: 'Search',
    searchPlaceholder: 'Search solutions...',
    newSolution: 'New Solution',
    guest: 'Guest',
    workspace: 'Workspace',
    primary: 'Primary',
    online: 'Online',
    offline: 'Offline',
    active: 'Active',
    connecting: 'Connecting...',
    sutraIntelligence: 'SUTRA Intelligence',
    sutraOrchestrator: 'SUTRA Orchestrator',
  },
  side: {
    dashboard: 'Dashboard',
    customBuilder: 'Custom Builder',
    legacyModernizer: 'Legacy Modernizer',
    solutions: 'Solutions',
    billing: 'Billing',
    deployKeys: 'Deploy Keys',
    admin: 'Admin',
    signOut: 'Sign out',
    guestUser: 'Guest User',
  },
  auth: {
    signIn: 'Sign in',
    signInSub: 'to your architecture workspace',
    continueAsGuest: 'Continue as Guest',
    noAccountNeeded: 'No account needed. Full demo access.',
    or: 'or',
    orEmail: 'or email',
    continueWithGithub: 'Continue with GitHub',
    continueWithGoogle: 'Continue with Google',
    email: 'Email',
    password: 'Password',
    signInWithEmail: 'Sign in with email',
    noAccount: 'No account?',
    createOne: 'Create one',
    createAccount: 'Create Account',
    createWorkspace: 'Create your workspace',
    createSub: 'Get 200 credits to generate and build MVPs',
    orgCompany: 'Organization / Company',
    yourFullName: 'Your Full Name',
    workEmail: 'Work Email',
    minPassword: 'Minimum 8 characters',
    signUpWithGithub: 'Sign up with GitHub',
    signUpWithGoogle: 'Sign up with Google',
    noRegistrationNeeded: 'No Registration Needed',
    tryDemoAsGuest: 'Try Demo As Guest (Unlimited Credits)',
    alreadyHaveAccount: 'Already have an account?',
    signInLink: 'Sign In',
  },
  dash: {
    overview: 'Overview',
    overviewSub:
      'Manage your intelligent solution blueprints, orchestrate AI swarm builds, and view your workspaces.',
    engineStatus: 'Engine Status',
    totalSolutions: 'Total Solutions',
    workspaces: 'Workspaces',
    activeBuilds: 'Active Builds',
    credits: 'Credits',
    aiSolutionBuilder: 'AI Solution Builder',
    aiSolutionBuilderDesc:
      'Design complex application architectures from a single natural language prompt. SUTRA will synthesize the domain, create the database schema, write APIs, and scaffold a complete frontend.',
    templates: 'Templates & Pre-builds',
    templatesSub: 'Instant scaffolding from verified industry patterns.',
    startNewBuild: 'Start a New Build Session',
    featContextual: 'Contextual Chat & Orchestration',
    featArchitecture: 'Live Architecture & HLD/LLD Generation',
    featDocs: 'Document parsing & PRD understanding',
    featScaffold: 'Instant Full-stack Next.js scaffolding',
  },
  chat: {
    aiArchitectWorkspace: 'AI Architect Workspace',
    synthesisEngine: 'Synthesis Engine',
    intelligenceLayer: 'Intelligence Layer',
    welcomeMessage:
      'I am SUTRA, your intelligence architect. Describe your application requirements, and I will synthesize a complete FastAPI + Next.js solution. Provide a PRD or spec for enhanced context, and select Build to finalize the architecture.',
    contextualData: 'Contextual Data',
    buildArtifacts: 'Build Artifacts',
    clearContext: 'Clear Context',
    providePrd:
      'Provide a PRD, specs, or schema. SUTRA will incorporate this into the architecture.',
    describeApp: 'Describe your application...',
    instructSutra: 'Instruct SUTRA (Context: {{filename}})...',
    appNameOptional: 'App Name (optional):',
    appNamePlaceholder: 'e.g. FitPulse Gym, Gourmet Bistro, PetHaven...',
    attachContext: 'Attach context',
    buildTab: 'Build',
    buildToggleHint:
      'Toggle BUILD before sending to generate a deployable MVP architecture.',
    awaitingSynthesis: 'Awaiting Synthesis',
    buildOrchestrated: 'Build Orchestrated',
    viewArtifacts: 'View Artifacts',
    buildingApplication: 'Building Application',
    executionMilestones: 'Execution Milestones',
    liveBuildLog: 'Live Build Log',
    synthesizingArchitecture: 'Synthesizing architecture...',
    buildingAppStatus: 'Building application:',
    stepLabel: 'Step',
    synthesizingStructure: 'Synthesizing application structure...',
    synthesisComplete: 'Synthesis complete.',
    initializingIntelligence: 'Initializing intelligence sequence…',
  },
  buildMilestones: {
    domainArchitecture: 'Domain Architecture & Specs',
    databaseSchema: 'Database & API Schema Registry',
    fullStackScaffold: 'Full-Stack Codebase Scaffold',
    domainModels: 'Domain Models & REST Routers',
    interactiveUi: 'Interactive UI Studios & Playground',
    codebaseVerification: 'Codebase Integrity Verification',
    productionPackage: 'Production Package Archive (.zip)',
  },
  voice: {
    voiceNote: 'Voice Note',
    recording: 'Recording',
    transcribing: 'Transcribing (Groq Whisper)...',
    stopRecordingTitle: 'Click to stop recording and transcribe',
    speakHint:
      'Speak in Gujarati, Hindi, English, or any language (Groq Whisper AI)',
  },
  lang: {
    language: 'Language',
  },
} as const;

type DeepStringify<T> = T extends string ? string : { [K in keyof T]: DeepStringify<T[K]> };

export type Dictionary = DeepStringify<typeof en>;

type DeepKeys<T, P extends string = ''> =
  T extends string
    ? P extends '' ? never : P
    : {
        [K in Extract<keyof T & string, string>]: DeepKeys<
          T[K],
          P extends '' ? K : `${P}.${K}`
        >;
      }[Extract<keyof T & string, string>];

export type TranslationKey = DeepKeys<Dictionary> & string;