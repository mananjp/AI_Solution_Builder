'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { getCurrentLanguage, setCurrentLanguage as persistLanguage } from '@/lib/api';

export interface LanguageOption {
  code: string;
  name: string;
  nativeName: string;
  flag?: string;
  script: string;
}

export const SUPPORTED_LANGUAGES: LanguageOption[] = [
  { code: 'en', name: 'English', nativeName: 'English', script: 'Latin' },
  { code: 'gu', name: 'Gujarati', nativeName: 'ગુજરાતી', script: 'Gujarati' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी', script: 'Devanagari' },
  { code: 'mr', name: 'Marathi', nativeName: 'मराठी', script: 'Devanagari' },
  { code: 'bn', name: 'Bengali', nativeName: 'বাংলা', script: 'Bengali' },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்', script: 'Tamil' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు', script: 'Telugu' },
  { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ', script: 'Kannada' },
  { code: 'ml', name: 'Malayalam', nativeName: 'മലയാളം', script: 'Malayalam' },
  { code: 'pa', name: 'Punjabi', nativeName: 'ਪੰਜਾਬੀ', script: 'Gurmukhi' },
  { code: 'es', name: 'Spanish', nativeName: 'Español', script: 'Latin' },
  { code: 'fr', name: 'French', nativeName: 'Français', script: 'Latin' },
  { code: 'de', name: 'German', nativeName: 'Deutsch', script: 'Latin' },
  { code: 'ja', name: 'Japanese', nativeName: '日本語', script: 'Japanese' },
  { code: 'ar', name: 'Arabic', nativeName: 'العربية', script: 'Arabic' },
];

export const UI_TRANSLATIONS: Record<string, Record<string, string>> = {
  workspace: {
    en: 'Workspace',
    gu: 'વર્કસ્પેસ',
    hi: 'कार्यस्थान',
    mr: 'कार्यक्षेत्र',
    bn: 'ওয়ার্কস্পেস',
    ta: 'பணியிடம்',
    te: 'వర్క్‌స్పేస్',
    kn: 'ಕೆಲಸದ ಸ್ಥಳ',
    ml: 'വർക്ക്സ്പേസ്',
    pa: 'ਵਰਕਸਪੇਸ',
    es: 'Espacio de trabajo',
    fr: 'Espace de travail',
    de: 'Arbeitsbereich',
  },
  newSolution: {
    en: 'New Solution',
    gu: 'નવો સોલ્યુશન',
    hi: 'नया समाधान',
    mr: 'नवीन सोल्यूशन',
    bn: 'নতুন সমাধান',
    ta: 'புதிய தீர்வு',
    te: 'కొత్త పరిష్కారం',
    kn: 'ಹೊಸ ಪರಿಹಾರ',
    ml: 'പുതിയ പരിഹാരം',
    pa: 'ਨਵਾਂ ਹੱਲ',
    es: 'Nueva solución',
    fr: 'Nouvelle solution',
    de: 'Neue Lösung',
  },
  searchSolutions: {
    en: 'Search solutions...',
    gu: 'સોલ્યુશન્સ શોધો...',
    hi: 'समाधान खोजें...',
    mr: 'सोल्यूशन्स शोधा...',
    bn: 'সমাধান খুঁজুন...',
    ta: 'தீர்வுகளைத் தேடு...',
    te: 'పరిష్కారాలను శోధించండి...',
    kn: 'ಪರಿಹಾರಗಳನ್ನು ಹುಡುಕಿ...',
    ml: 'പരിഹാരങ്ങൾ തിരയുക...',
    pa: 'ਹੱਲ ਖੋਜੋ...',
    es: 'Buscar soluciones...',
    fr: 'Rechercher des solutions...',
    de: 'Lösungen suchen...',
  },
  describeApp: {
    en: 'Describe your application (e.g. gym tracker, clinic management, e-commerce)...',
    gu: 'તમારી એપ્લિકેશનનું વર્ણન કરો (દા.ત. જિમ ટ્રેકર, ક્લિનિક મેનેજમેન્ટ, ઈ-કોમર્સ)...',
    hi: 'अपने एप्लिकेशन का विवरण दें (उदा. जिम ट्रैकर, क्लिनिक प्रबंधन, ई-कॉमर्स)...',
    mr: 'आपल्या अनुप्रयोगाचे वर्णन करा (उदा. जिम ट्रॅकर, क्लिनिक व्यवस्थापन, ई-कॉमर्स)...',
    bn: 'আপনার অ্যাপ্লিকেশনের বর্ণনা দিন (যেমন জিম ট্র্যাকার, ক্লিনিক ব্যবস্থাপনা)...',
    ta: 'உங்கள் பயன்பாட்டை விவரிக்கவும் (எ.கா. ஜிம் டிராக்கர், மருத்துவமனை)...',
    te: 'మీ అప్లికేషన్‌ను వివరించండి (ఉదా. జిమ్ ట్రాకర్, క్లినిక్ నిర్వహణ)...',
    kn: 'ನಿಮ್ಮ ಅಪ್ಲಿಕೇಶನ್ ವಿವರಿಸಿ...',
    ml: 'നിങ്ങളുടെ ആപ്ലിക്കേഷൻ വിവരിക്കുക...',
    pa: 'ਆਪਣੀ ਐਪਲੀਕੇਸ਼ਨ ਦਾ ਵਰਣਨ ਕਰੋ...',
    es: 'Describa su aplicación...',
    fr: 'Décrivez votre application...',
    de: 'Beschreiben Sie Ihre Anwendung...',
  },
  build: {
    en: 'Build',
    gu: 'બિલ્ડ',
    hi: 'बिल्ड',
    mr: 'बिल्ड',
    bn: 'বিল্ড',
    ta: 'உருவாக்கு',
    te: 'బిల్డ్',
    kn: 'ನಿರ್ಮಿಸಿ',
    ml: 'നിർമ്മിക്കുക',
    pa: 'ਬਣਾਓ',
    es: 'Construir',
    fr: 'Construire',
    de: 'Erstellen',
  },
  buildApplication: {
    en: 'Build Application',
    gu: 'એપ્લિકેશન બનાવો',
    hi: 'एप्लिकेशन बनाएं',
    mr: 'अनुप्रयोग तयार करा',
    bn: 'অ্যাপ্লিকেশন তৈরি করুন',
    ta: 'பயன்பாட்டை உருவாக்கவும்',
    te: 'అప్లికేషన్ నిర్మించండి',
    kn: 'ಅಪ್ಲಿಕೇಶನ್ ನಿರ್ಮಿಸಿ',
    ml: 'ആപ്ലിക്കേഷൻ നിർമ്മിക്കുക',
    pa: 'ਐਪਲੀਕੇਸ਼ਨ ਬਣਾਓ',
    es: 'Construir aplicación',
    fr: 'Construire l’application',
    de: 'Anwendung erstellen',
  },
  buildArtifacts: {
    en: 'Build Artifacts',
    gu: 'બિલ્ડ આર્ટિફેક્ટ્સ',
    hi: 'बिल्ड आर्टिफैक्ट्स',
    mr: 'बिल्ड आर्टिफॅक्ट्स',
    bn: 'বিল্ড আর্টিফ্যাক্টস',
    ta: 'கட்டமைப்பு கலைப்பொருட்கள்',
    te: 'బిల్డ్ కళాఖండాలు',
    kn: 'ಕಲಾಕೃತಿಗಳನ್ನು ನಿರ್ಮಿಸಿ',
    ml: 'ആർട്ടിഫാക്റ്റുകൾ നിർമ്മിക്കുക',
    pa: 'ਆਰਟੀਫੈਕਟ ਬਣਾਓ',
    es: 'Artefactos de construcción',
    fr: 'Artefacts de build',
    de: 'Build-Artefakte',
  },
  voiceNote: {
    en: 'Voice Note',
    gu: 'વોઇસ નોટ',
    hi: 'आवाज़ नोट',
    mr: 'व्हॉइस टीप',
    bn: 'ভয়েস নোট',
    ta: 'குரல் குறிப்பு',
    te: 'వాయిస్ నోట్',
    kn: 'ಧ್ವನಿ ಟಿಪ್ಪಣಿ',
    ml: 'വോയ്‌സ് കുറിപ്പ്',
    pa: 'ਵੌਇਸ ਨੋਟ',
    es: 'Nota de voz',
    fr: 'Note vocale',
    de: 'Sprachnotiz',
  },
  recording: {
    en: 'Recording',
    gu: 'રેકોર્ડિંગ',
    hi: 'रिकॉर्डिंग',
    mr: 'रेकॉर्डिंग',
    bn: 'রেকর্ডিং',
    ta: 'பதிவு செய்கிறது',
    te: 'రికార్డింగ్',
    kn: 'ರೆಕಾರ್ಡಿಂಗ್',
    ml: 'റെക്കോർഡിംഗ്',
    pa: 'ਰਿਕਾਰਡਿੰਗ',
    es: 'Grabando',
    fr: 'Enregistrement',
    de: 'Aufnahme',
  },
  transcribing: {
    en: 'Transcribing (Groq Whisper)...',
    gu: 'ટ્રાંસ્ક્રાઇબ થઈ રહ્યું છે (Groq Whisper)...',
    hi: 'ट्रांसक्राइब हो रहा है (Groq Whisper)...',
    mr: 'लिप्यंतरण सुरू आहे (Groq Whisper)...',
    bn: 'ট্রান্সক্রাইব হচ্ছে (Groq Whisper)...',
    ta: 'எழுத்தாக்கம் செய்யப்படுகிறது (Groq Whisper)...',
    te: 'ట్రాన్స్‌క్రైబ్ అవుతోంది (Groq Whisper)...',
    kn: 'ಪ್ರತಿಯಾಗಿಸುತ್ತಿದೆ (Groq Whisper)...',
    ml: 'ട്രാൻസ്ക്രൈബ് ചെയ്യുന്നു (Groq Whisper)...',
    pa: 'ਟ੍ਰਾਂਸਕ੍ਰਾਈਬ ਕੀਤਾ ਜਾ ਰਿਹਾ ਹੈ (Groq Whisper)...',
    es: 'Transcribiendo (Groq Whisper)...',
    fr: 'Transcription (Groq Whisper)...',
    de: 'Transkribieren (Groq Whisper)...',
  },
  liveSandbox: {
    en: 'Live Sandbox',
    gu: 'લાઇવ સેન્ડબોક્સ',
    hi: 'लाइव सैंडबॉक्स',
    mr: 'लाइव्ह सँडबॉक्स',
    bn: 'লাইভ স্যান্ডবক্স',
    ta: 'நேரடி சாண்ட்பாக்ஸ்',
    te: 'లైవ్ శాండ్‌బాక్స్',
    kn: 'ಲೈವ್ ಸ್ಯಾಂಡ್‌ಬಾಕ್ಸ್',
    ml: 'ലൈവ് സാൻഡ്‌ബോക്സ്',
    pa: 'ਲਾਈਵ ਸੈਂਡਬੌਕਸ',
    es: 'Sandbox en vivo',
    fr: 'Bac à sable en direct',
    de: 'Live-Sandbox',
  },
  deploy: {
    en: 'Deploy',
    gu: 'ડિપ્લોય કરો',
    hi: 'डिप्लॉय करें',
    mr: 'डिप्लॉय करा',
    bn: 'ডিপ্লয় করুন',
    ta: 'பயன்படுத்து',
    te: 'డిప్లాయ్ చేయండి',
    kn: 'ನಿಯೋಜಿಸಿ',
    ml: 'വിന്യസിക്കുക',
    pa: 'ਡਿਪਲਾਏ ਕਰੋ',
    es: 'Desplegar',
    fr: 'Déployer',
    de: 'Bereitstellen',
  },
  downloadZip: {
    en: 'Download .ZIP',
    gu: '.ZIP ડાઉનલોડ કરો',
    hi: '.ZIP डाउनलोड करें',
    mr: '.ZIP डाउनलोड करा',
    bn: '.ZIP ডাউনলোড করুন',
    ta: '.ZIP பதிவிறக்கு',
    te: '.ZIP డౌన్‌లోడ్ చేయండి',
    kn: '.ZIP ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ',
    ml: '.ZIP ഡൗൺലോഡ് ചെയ്യുക',
    pa: '.ZIP ਡਾਊਨਲੋਡ ਕਰੋ',
    es: 'Descargar .ZIP',
    fr: 'Télécharger .ZIP',
    de: '.ZIP herunterladen',
  },
  language: {
    en: 'Language',
    gu: 'ભાષા',
    hi: 'भाषा',
    mr: 'भाषा',
    bn: 'ভাষা',
    ta: 'மொழி',
    te: 'భాష',
    kn: 'ಭಾಷೆ',
    ml: 'ഭാഷ',
    pa: 'ਭਾਸ਼ਾ',
    es: 'Idioma',
    fr: 'Langue',
    de: 'Sprache',
  },
};

interface LanguageContextType {
  language: string;
  setLanguage: (code: string) => void;
  currentOption: LanguageOption;
  t: (key: string, fallback?: string) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'en',
  setLanguage: () => {},
  currentOption: SUPPORTED_LANGUAGES[0],
  t: (key, fallback) => fallback || key,
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<string>(() => {
    return getCurrentLanguage();
  });

  useEffect(() => {
    try {
      document.documentElement.lang = language;
    } catch {
      // ignore
    }
  }, [language]);

  const setLanguage = (code: string) => {
    setLanguageState(code);
    persistLanguage(code);
  };

  const currentOption =
    SUPPORTED_LANGUAGES.find((opt) => opt.code === language) || SUPPORTED_LANGUAGES[0];

  const t = (key: string, fallback?: string): string => {
    const entry = UI_TRANSLATIONS[key];
    if (!entry) return fallback || key;
    return entry[language] || entry['en'] || fallback || key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, currentOption, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
