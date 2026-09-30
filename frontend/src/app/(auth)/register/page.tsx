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
 * Create an account.
 *
 * Registration is Auth0's Universal Login with `screen_hint=signup`, so a
 * brand-new user lands on the tenant's own "Create account" form with whatever
 * social connections that tenant has enabled. We collect nothing: an email and
 * password collected here would be a second credential store to secure, and an
 * `org_name` field here could not be validated for uniqueness the way an Auth0
 * Organization can.
 */
function RegisterForm() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const { loginWithRedirect } = useAuth0();
  const { isMisconfigured, isAuthenticated, isLoading } = useAuthSession();
  const [isRedirecting, setIsRedirecting] = useState(false);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="size-4 animate-spin text-muted" />
      </div>
    );
  }

  if (isAuthenticated) {
    return (
      <Card>
        <CardContent className="space-y-4 p-8 text-center">
          <p className="text-[13px] text-muted">{t('auth.alreadySignedIn')}</p>
          <Button asChild className="w-full py-3">
            <Link href="/dashboard">{t('auth.goToDashboard')}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const handleSignup = async () => {
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
        authorizationParams: { screen_hint: 'signup' },
        appState: { returnTo: returnTo && returnTo.startsWith('/') ? returnTo : '/dashboard' },
      });
    } catch (err) {
      logError('failed to start the Auth0 signup redirect', err);
      setIsRedirecting(false);
      toast.error('Could not reach the sign-up page', {
        description: 'Check your connection and try again.',
      });
    }
  };

  return (
    <div className="space-y-4">
      {isMisconfigured && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>
            Auth0 is not configured. Set{' '}
            <code className="font-mono">NEXT_PUBLIC_AUTH0_DOMAIN</code> and{' '}
            <code className="font-mono">NEXT_PUBLIC_AUTH0_CLIENT_ID</code>, then rebuild.
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardContent className="space-y-6 p-8">
          <Button
            id="auth0-signup-btn"
            size="lg"
            className="w-full shadow-md"
            onClick={handleSignup}
            disabled={isRedirecting || isMisconfigured}
          >
            {isRedirecting ? <Loader2 className="animate-spin" /> : <Sparkles />}
            {t('auth.createAccount')}
          </Button>

          <p className="flex items-start gap-2.5 text-[12px] font-light leading-relaxed text-muted">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-foreground" />
            {t('auth.createAccountSub')}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function RegisterPage() {
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
          <h1 className="font-serif text-2xl">{t('auth.createAccountTitle')}</h1>
          <p className="mt-2 text-[13px] font-light text-muted">
            {t('auth.createAccountSub')}
          </p>
        </div>

        <Suspense
          fallback={
            <div className="flex justify-center py-10">
              <Loader2 className="size-4 animate-spin text-muted" />
            </div>
          }
        >
          <RegisterForm />
        </Suspense>

        <p className="mt-6 text-center text-[12px] text-muted">
          {t('auth.haveAccount')}{' '}
          <Link
            href="/login"
            className="border-b border-foreground pb-0.5 font-semibold transition-colors hover:border-foreground hover:text-foreground"
          >
            {t('auth.signIn')}
          </Link>
        </p>
      </div>
    </div>
  );
}
