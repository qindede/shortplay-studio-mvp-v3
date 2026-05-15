import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND = env.BACKEND_URL || 'http://localhost:8000';

export const GET: RequestHandler = async ({ params, request }) => {
  return proxy(params.path, request);
};

export const POST: RequestHandler = async ({ params, request }) => {
  return proxy(params.path, request, 'POST');
};

export const PUT: RequestHandler = async ({ params, request }) => {
  return proxy(params.path, request, 'PUT');
};

export const PATCH: RequestHandler = async ({ params, request }) => {
  return proxy(params.path, request, 'PATCH');
};

export const DELETE: RequestHandler = async ({ params, request }) => {
  return proxy(params.path, request, 'DELETE');
};

async function proxy(path: string, request: Request, method?: string) {
  const headers = new Headers();
  const token = request.headers.get('x-user-token');
  if (token) headers.set('X-User-Token', token);

  const contentType = request.headers.get('content-type');
  if (contentType) headers.set('Content-Type', contentType);

  const res = await fetch(`${BACKEND}/api/${path}`, {
    method: method || request.method,
    headers,
    body: ['GET', 'HEAD'].includes(method || request.method) ? undefined : await request.arrayBuffer()
  });

  return new Response(res.body, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' }
  });
}
