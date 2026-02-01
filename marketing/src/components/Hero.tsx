'use client'

import Link from 'next/link'

export default function Hero() {
  return (
    <section className="relative bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 text-white overflow-hidden">
      <div className="absolute inset-0 bg-[url('/grid.svg')] bg-center opacity-10" />
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 sm:py-32">
        <div className="text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6">
            AI-Powered Prior Auth Intelligence
          </h1>
          <p className="max-w-2xl mx-auto text-lg sm:text-xl text-blue-100 mb-10">
            Transform your healthcare revenue cycle with intelligent prior authorization
            automation. Reduce denials, accelerate approvals, and improve patient outcomes.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center px-8 py-4 text-lg font-semibold rounded-lg bg-white text-blue-900 hover:bg-blue-50 transition-colors shadow-lg hover:shadow-xl"
            >
              Start Free Trial
            </Link>
            <Link
              href="/demo"
              className="inline-flex items-center justify-center px-8 py-4 text-lg font-semibold rounded-lg border-2 border-white text-white hover:bg-white/10 transition-colors"
            >
              Schedule Demo
            </Link>
          </div>
        </div>
        <div className="mt-16 flex justify-center">
          <div className="grid grid-cols-3 gap-8 text-center">
            <div>
              <div className="text-3xl sm:text-4xl font-bold">85%</div>
              <div className="text-blue-200 text-sm sm:text-base">Faster Approvals</div>
            </div>
            <div>
              <div className="text-3xl sm:text-4xl font-bold">60%</div>
              <div className="text-blue-200 text-sm sm:text-base">Fewer Denials</div>
            </div>
            <div>
              <div className="text-3xl sm:text-4xl font-bold">40%</div>
              <div className="text-blue-200 text-sm sm:text-base">Cost Reduction</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
