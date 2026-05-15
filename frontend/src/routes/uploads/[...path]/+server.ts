import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND = env.BACKEND_URL || 'http://localhost:8000';

export const GET: RequestHandler = async ({ params }) => {
  const res = await fetch(`${BACKEND}/uploads/${params.path}`);
  return new Response(res.body, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/octet-stream' }
  });
};
