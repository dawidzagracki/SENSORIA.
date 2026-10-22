/**
 * Simplified marks of the payment and delivery brands shown next to their names.
 * They are drawn as inline SVG so nothing loads from a third party; swap in the official brand
 * assets (from each provider's brand guidelines) before the production launch.
 */
import type { ReactNode } from "react";

type LogoProps = { className?: string };

function Badge({
  label,
  className = "",
  children,
  width = 56,
}: {
  label: string;
  className?: string;
  children: ReactNode;
  width?: number;
}) {
  return (
    <svg
      aria-label={label}
      className={`h-7 w-auto shrink-0 ${className}`}
      role="img"
      viewBox={`0 0 ${width} 28`}
    >
      <title>{label}</title>
      <rect
        fill="#fff"
        height="26"
        rx="8"
        stroke="#e7d3dc"
        strokeWidth="1"
        width={width - 2}
        x="1"
        y="1"
      />
      {children}
    </svg>
  );
}

export function BlikLogo({ className }: LogoProps) {
  return (
    <Badge className={className} label="BLIK">
      <text
        fill="#111"
        fontFamily="Plus Jakarta Sans Variable, system-ui, sans-serif"
        fontSize="13"
        fontWeight="800"
        x="9"
        y="19"
      >
        blik
      </text>
      <circle cx="43" cy="11" fill="#e5004c" r="2.2" />
      <circle cx="48" cy="15" fill="#009de0" r="2.2" />
    </Badge>
  );
}

export function VisaLogo({ className }: LogoProps) {
  return (
    <Badge className={className} label="Visa">
      <text
        fill="#1a1f71"
        fontFamily="Plus Jakarta Sans Variable, system-ui, sans-serif"
        fontSize="13"
        fontStyle="italic"
        fontWeight="800"
        x="9"
        y="19"
      >
        VISA
      </text>
    </Badge>
  );
}

export function MastercardLogo({ className }: LogoProps) {
  return (
    <Badge className={className} label="Mastercard">
      <circle cx="22" cy="14" fill="#eb001b" r="8" />
      <circle cx="34" cy="14" fill="#f79e1b" r="8" />
      <path d="M28 7.6a8 8 0 0 1 0 12.8 8 8 0 0 1 0-12.8z" fill="#ff5f00" />
    </Badge>
  );
}

export function GooglePayLogo({ className }: LogoProps) {
  return (
    <Badge className={className} label="Google Pay" width={64}>
      <text
        fontFamily="Plus Jakarta Sans Variable, system-ui, sans-serif"
        fontSize="13"
        fontWeight="800"
        x="9"
        y="19"
      >
        <tspan fill="#4285f4">G</tspan>
        <tspan fill="#5f6368"> Pay</tspan>
      </text>
    </Badge>
  );
}

export function ApplePayLogo({ className }: LogoProps) {
  return (
    <Badge className={className} label="Apple Pay" width={64}>
      <path
        d="M17.6 9.4c.7-.8 1.1-1.9 1-3-.9 0-2 .6-2.7 1.4-.6.7-1.1 1.8-1 2.9 1 .1 2-.5 2.7-1.3zm1 1.6c-1.5-.1-2.8.9-3.5.9-.7 0-1.8-.8-3-.8-1.5 0-3 .9-3.8 2.3-1.6 2.8-.4 7 1.2 9.3.8 1.1 1.700 2.400 2.900 2.300 1.100 0 1.600-.7 3-.7s1.800.7 3 .7c1.300 0 2.100-1.100 2.900-2.300.9-1.300 1.300-2.500 1.300-2.600-.1 0-2.500-1-2.500-3.800 0-2.300 1.900-3.400 2-3.500-1.100-1.600-2.800-1.800-3.500-1.800z"
        fill="#111"
        transform="translate(1 -3.500) scale(.78)"
      />
      <text
        fill="#111"
        fontFamily="Plus Jakarta Sans Variable, system-ui, sans-serif"
        fontSize="12"
        fontWeight="800"
        x="26"
        y="19"
      >
        Pay
      </text>
    </Badge>
  );
}

export function InPostLogo({ className }: LogoProps) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      alt="InPost"
      className={`h-10 w-auto shrink-0 ${className ?? ""}`}
      height={241}
      src="/brand/inpost.png"
      width={400}
    />
  );
}

export function StripeLogo({ className }: LogoProps) {
  return (
    <svg
      aria-label="Stripe"
      className={`h-7 w-auto shrink-0 ${className ?? ""}`}
      role="img"
      viewBox="0 0 64 28"
    >
      <title>Stripe</title>
      <rect fill="#635bff" height="28" rx="9" width="64" />
      <text
        fill="#fff"
        fontFamily="Plus Jakarta Sans Variable, system-ui, sans-serif"
        fontSize="13"
        fontWeight="800"
        x="9"
        y="19"
      >
        stripe
      </text>
    </svg>
  );
}

/** Multi-colour Google "G" used on the sign-in button. */
export function GoogleMark({ className = "h-5 w-5" }: LogoProps) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 48 48">
      <path
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
        fill="#EA4335"
      />
      <path
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
        fill="#4285F4"
      />
      <path
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
        fill="#FBBC05"
      />
      <path
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
        fill="#34A853"
      />
    </svg>
  );
}

export function PaymentLogos({ className = "" }: LogoProps) {
  return (
    <span className={`flex flex-wrap items-center gap-2 ${className}`}>
      <BlikLogo />
      <VisaLogo />
      <MastercardLogo />
      <GooglePayLogo />
      <ApplePayLogo />
    </span>
  );
}
