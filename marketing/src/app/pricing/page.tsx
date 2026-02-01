'use client'

import { useState } from 'react'
import PricingCard from '@/components/PricingCard'

const pricingTiers = [
  {
    name: 'Essentials',
    monthlyPrice: 299,
    description: 'For small practices getting started with prior auth automation',
    cta: 'Start Free Trial',
    features: [
      { text: 'Up to 500 claims/month', included: true },
      { text: 'Basic prior auth automation', included: true },
      { text: 'Email support', included: true },
      { text: 'Standard analytics dashboard', included: true },
      { text: 'Single user access', included: true },
      { text: 'API access', included: false },
      { text: 'Custom integrations', included: false },
      { text: 'Dedicated account manager', included: false },
    ],
  },
  {
    name: 'Professional',
    monthlyPrice: 599,
    description: 'For growing practices that need advanced features',
    cta: 'Start Free Trial',
    popular: true,
    features: [
      { text: 'Up to 2,500 claims/month', included: true },
      { text: 'Advanced prior auth automation', included: true },
      { text: 'Priority email & chat support', included: true },
      { text: 'Advanced analytics & reporting', included: true },
      { text: 'Up to 10 user accounts', included: true },
      { text: 'API access', included: true },
      { text: 'EHR integrations', included: true },
      { text: 'Dedicated account manager', included: false },
    ],
  },
  {
    name: 'Enterprise',
    monthlyPrice: 999,
    description: 'For large organizations with complex requirements',
    cta: 'Contact Sales',
    features: [
      { text: 'Unlimited claims', included: true },
      { text: 'Enterprise prior auth automation', included: true },
      { text: '24/7 phone & email support', included: true },
      { text: 'Custom analytics & dashboards', included: true },
      { text: 'Unlimited users', included: true },
      { text: 'Full API access', included: true },
      { text: 'Custom integrations', included: true },
      { text: 'Dedicated account manager', included: true },
    ],
  },
]

export default function PricingPage() {
  const [isAnnual, setIsAnnual] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="text-center mb-16">
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
            Choose the plan that fits your practice. All plans include a 14-day free trial.
          </p>
          <div className="flex items-center justify-center gap-4">
            <span className={`text-sm font-medium ${!isAnnual ? 'text-gray-900' : 'text-gray-500'}`}>
              Monthly
            </span>
            <button
              onClick={() => setIsAnnual(!isAnnual)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                isAnnual ? 'bg-blue-600' : 'bg-gray-300'
              }`}
              aria-label="Toggle annual billing"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isAnnual ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            <span className={`text-sm font-medium ${isAnnual ? 'text-gray-900' : 'text-gray-500'}`}>
              Annual
            </span>
            {isAnnual && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                2 months free
              </span>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12 items-start">
          {pricingTiers.map((tier) => (
            <PricingCard key={tier.name} tier={tier} isAnnual={isAnnual} />
          ))}
        </div>
        <div className="mt-16 text-center">
          <p className="text-gray-600 mb-4">
            Need a custom solution? We&apos;re here to help.
          </p>
          <a
            href="/contact"
            className="text-blue-600 font-semibold hover:text-blue-700"
          >
            Contact our sales team →
          </a>
        </div>
      </div>
    </div>
  )
}
