// Receives Stripe webhook events and keeps the `subscriptions` table (see
// supabase/schema.sql) in sync. This is the ONLY custom backend code in the
// whole project -- every other part of the paywall (trial expiry, entitlement
// checks) is enforced by Postgres Row Level Security policies, not here.
//
// Required secrets (set once via `supabase secrets set`, never committed):
//   STRIPE_API_KEY               - Stripe Dashboard -> Developers -> API keys
//   STRIPE_WEBHOOK_SIGNING_SECRET - shown when you create the webhook endpoint
//                                   in the Stripe Dashboard, pointed at this
//                                   function's deployed URL
//
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are injected automatically into
// every Edge Function by Supabase -- nothing to set for those.
//
// Deployed with verify_jwt = false (see supabase/config.toml) because Stripe
// calls this endpoint directly and has no Supabase login of its own --
// the Stripe signature check below is what verifies the caller instead.

import Stripe from 'npm:stripe@^22'
import { createClient } from 'npm:@supabase/supabase-js@2'

const stripe = new Stripe(Deno.env.get('STRIPE_API_KEY') as string)

// Deno doesn't have Node's synchronous crypto, so Stripe's SDK needs this
// explicit SubtleCrypto-based provider to verify the webhook signature.
const cryptoProvider = Stripe.createSubtleCryptoProvider()

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)

async function upsertSubscription(fields: Record<string, unknown>) {
  const { error } = await supabase
    .from('subscriptions')
    .upsert(fields, { onConflict: 'user_id' })
  if (error) console.error('Failed to upsert subscription:', error)
}

async function findUserIdBySubscription(stripeSubscriptionId: string) {
  const { data, error } = await supabase
    .from('subscriptions')
    .select('user_id')
    .eq('stripe_subscription_id', stripeSubscriptionId)
    .maybeSingle()
  if (error) console.error('Lookup failed:', error)
  return data?.user_id as string | undefined
}

Deno.serve(async (req) => {
  const signature = req.headers.get('Stripe-Signature')
  // constructEventAsync needs the RAW body -- not req.json() -- or signature
  // verification fails.
  const body = await req.text()

  let event: Stripe.Event
  try {
    event = await stripe.webhooks.constructEventAsync(
      body,
      signature!,
      Deno.env.get('STRIPE_WEBHOOK_SIGNING_SECRET')!,
      undefined,
      cryptoProvider
    )
  } catch (err) {
    console.error('Webhook signature verification failed:', err)
    return new Response(`Webhook Error: ${(err as Error).message}`, { status: 400 })
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object as Stripe.Checkout.Session
        // We pass the Supabase user id as client_reference_id when building
        // the Payment Link URL from the site -- this is how we know WHO paid.
        const userId = session.client_reference_id
        if (!userId) {
          console.error('checkout.session.completed had no client_reference_id')
          break
        }

        const subscriptionId = session.subscription as string | null
        let currentPeriodEnd: string | null = null
        if (subscriptionId) {
          const sub = await stripe.subscriptions.retrieve(subscriptionId)
          currentPeriodEnd = new Date(sub.current_period_end * 1000).toISOString()
        }

        await upsertSubscription({
          user_id: userId,
          stripe_customer_id: session.customer as string,
          stripe_subscription_id: subscriptionId,
          status: 'active',
          current_period_end: currentPeriodEnd,
          updated_at: new Date().toISOString(),
        })
        break
      }

      case 'customer.subscription.updated':
      case 'customer.subscription.deleted': {
        const sub = event.data.object as Stripe.Subscription
        const userId = await findUserIdBySubscription(sub.id)
        if (!userId) {
          console.error('No matching subscription row for', sub.id)
          break
        }
        await upsertSubscription({
          user_id: userId,
          stripe_subscription_id: sub.id,
          status: event.type === 'customer.subscription.deleted' ? 'canceled' : sub.status,
          current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        })
        break
      }

      case 'invoice.payment_failed': {
        const invoice = event.data.object as Stripe.Invoice
        const subscriptionId = invoice.subscription as string | null
        if (!subscriptionId) break
        const userId = await findUserIdBySubscription(subscriptionId)
        if (!userId) break
        await upsertSubscription({
          user_id: userId,
          stripe_subscription_id: subscriptionId,
          status: 'past_due',
          updated_at: new Date().toISOString(),
        })
        break
      }

      default:
        // Other event types are ignored -- nothing else affects entitlement.
        break
    }
  } catch (err) {
    console.error('Error handling webhook event', event.type, err)
    return new Response('Internal error', { status: 500 })
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { 'Content-Type': 'application/json' },
  })
})
