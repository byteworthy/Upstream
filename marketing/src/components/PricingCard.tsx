'use client'

import Link from 'next/link'

interface PricingFeature {
  text: string
  included: boolean
}

interface PricingTier {
  name: string
  monthlyPrice: number
  description: string
  features: PricingFeature[]
  cta: string
  popular?: boolean
}

interface PricingCardProps {
  tier: PricingTier
  isAnnual: boolean
}

export default function PricingCard({ tier, isAnnual }: PricingCardProps) {
  const price = isAnnual
    ? Math.round(tier.monthlyPrice * 10 / 12)
    : tier.monthlyPrice

  return (
    <div
      className={`relative flex flex-col p-8 bg-white rounded-2xl shadow-lg ${
        tier.popular
          ? 'ring-2 ring-blue-600 scale-105'
          : 'border border-gray-200'
      }`}
    >
      {tier.popular && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2">
          <span className="inline-flex items-center px-4 py-1 rounded-full text-sm font-semibold bg-blue-600 text-white">
            Most Popular
          </span>
        </div>
      )}
      <div className="text-center mb-8">
        <h3 className="text-xl font-bold text-gray-900 mb-2">{tier.name}</h3>
        <p className="text-gray-500 text-sm mb-4">{tier.description}</p>
        <div className="flex items-baseline justify-center gap-1">
          <span className="text-4xl font-bold text-gray-900">${price}</span>
          <span className="text-gray-500">/month</span>
        </div>
        {isAnnual && (
          <p className="text-sm text-green-600 mt-2">
            Save ${tier.monthlyPrice * 2}/year
          </p>
        )}
      </div>
      <ul className="space-y-4 mb-8 flex-grow">
        {tier.features.map((feature, index) => (
          <li key={index} className="flex items-start gap-3">
            {feature.included ? (
              <svg
                className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5 text-gray-300 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            )}
            <span className={feature.included ? 'text-gray-700' : 'text-gray-400'}>
              {feature.text}
            </span>
          </li>
        ))}
      </ul>
      <Link
        href="/signup"
        className={`block w-full py-3 px-6 text-center font-semibold rounded-lg transition-colors ${
          tier.popular
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
        }`}
      >
        {tier.cta}
      </Link>
    </div>
  )
}
