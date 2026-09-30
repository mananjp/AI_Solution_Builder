'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AlertCircle, Loader2, ShieldCheck, Sparkles } from 'lucide-react';
import { useAuth0 } from '@auth0/auth0-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { useI18n } from '@/components/I18nProvider';
import { LanguageSelector } from '@/components/LanguageSelector';
import { useAuthSession } from '@/components/auth/AuthProvider';
import { logError } from '@/lib/logger';

/**
 * Sign in.
 *
 * There is deliberately no email/password field here. Auth0's Universal Login
 * is the single credential authority: it hosts the password reset, MFA, brute
 * force protection, and every social connection, none of which we could
 * reimplement correctly. Collecting credentials here would mean a second
 * password store to breach and a second surface to keep patched.
 */
function LoginForm() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const { loginWithRedirect } = useAuth0();
  const { isMisconfigured, isAuthenticated, isLoading } = useAuthSession();
  const [isRedirecting, setIsRedirecting] = useState(false);

  // Reached only while a real Auth0 session is being restored. A misconfigured
  // build reports settled immediately, so it falls through to the explanation
  // below instead of spinning forever.
  if (isLoading) {
    return (
      <div className="flex justify-center py-10" role="status" aria-label="Checking session">
        <Loader2 className="size-4 animate-spin text-muted" />
      </div>
    );
  }

  if (isAuthenticated) {
    return (
      <Card>
        <CardContent className="space-y-4 p-8 text-center">
          <p className="text-[13px] text-muted">
            You already have an account and are signed in.
          </p>
          <Button asChild className="w-full py-3">
            <Link href="/dashboard">{t('auth.goToDashboard')}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const handleSignIn = async () => {
    if (isMisconfigured) {
      toast.error('Authentication is not configured', {
        description:
          'Set NEXT_PUBLIC_AUTH0_DOMAIN and NEXT_PUBLIC_AUTH0_CLIENT_ID, then rebuild the frontend.',
      });
      return;
    }
    setIsRedirecting(true);
    try {
      const returnTo = searchParams.get('returnTo');
      await loginWithRedirect({
        appState: { returnTo: returnTo && returnTo.startsWith('/') ? returnTo : '/dashboard' },
      });
    } catch (err) {
      logError('failed to start the Auth0 login redirect', err);
      setIsRedirecting(false);
      toast.error('Could not reach the sign-in page', {
        description: 'Check your connection and try again.',
      });
    }
  };

  return (
    <div className="space-y-4">
      {isMisconfigured ? (
        // Nothing can sign in, so say so plainly and stop. Previously the page
        // offered a permanently disabled button, which looked broken rather than
        // unconfigured.
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>
            <p className="font-semibold">Authentication is not configured</p>
            <p className="mt-1">
              This build has no Auth0 tenant, so sign-in is unavailable. Set{' '}
              <code className="font-mono">NEXT_PUBLIC_AUTH0_DOMAIN</code> and{' '}
              <code className="font-mono">NEXT_PUBLIC_AUTH0_CLIENT_ID</code>, then rebuild
              the frontend.
            </p>
          </AlertDescription>
        </Alert>
      ) : (
        <Card>
          <CardContent className="space-y-6 p-8">
            <Button
              id="auth0-login-btn"
              size="lg"
              className="w-full"
              onClick={handleSignIn}
              disabled={isRedirecting}
            >
              {isRedirecting ? <Loader2 className="animate-spin" /> : <Sparkles />}
              {isRedirecting ? t('common.connecting') : t('auth.signIn')}
            </Button>

            <p className="flex items-start gap-2.5 text-[12px] font-light leading-relaxed text-muted">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-foreground" />
              {t('auth.signInDisclaimer')}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Still a way forward when sign-in cannot work. */}
      <Card>
        <CardContent className="space-y-3 p-6 text-center">
          <p className="text-[13px] text-muted">
            {t('auth.noAccount')}{' '}
            <Link
              href="/register"
              className="font-semibold text-foreground underline underline-offset-4"
            >
              {t('auth.createAccount')}
            </Link>
          </p>
          <p className="text-[12px] text-muted">
            <Link href="/" className="underline underline-offset-4 hover:text-foreground">
              {t('auth.backToHome')}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  const { t } = useI18n();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-100 animate-fade-up">
        <div className="mb-10 text-center">
          <Link href="/" className="mb-6 inline-flex w-full items-center justify-center">
            <span className="text-5xl font-bold leading-none text-foreground drop-shadow-sm">
              सूत्र
            </span>
          </Link>
          <div className="mb-4 flex items-center justify-center gap-3">
            <LanguageSelector compact />
          </div>
          <h1 className="font-serif text-2xl">{t('auth.welcomeBack')}</h1>
          <p className="mt-2 text-[13px] font-light text-muted">{t('auth.signInSub')}</p>
        </div>

        <Suspense
          fallback={
            <div className="flex justify-center py-10">
              <Loader2 className="size-4 animate-spin text-muted" />
            </div>
          }
        >
          <LoginForm />
        </Suspense>
      </div>
    </div>
  );
}
