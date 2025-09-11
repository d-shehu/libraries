import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { jwtDecode } from 'jwt-decode';

export interface JWTPayload {
  email:    string;
  id:       string;
  expires:  string;
  permissions: string[];
}

@Injectable({
  providedIn: 'root'
})
export class Auth {
  private accessToken$ = new BehaviorSubject<string | null>(null);
  private userPayload$ = new BehaviorSubject<JWTPayload | null>(null);

  constructor(private http: HttpClient) { }

  /** Get current token */
  get token(): string | null {
    return this.accessToken$.value;
  }

  get user(): Observable<JWTPayload | null> {
    return this.userPayload$.asObservable();
  }

  get isLoggedIn(): boolean {
    return !!this.accessToken$.value;
  }

  /** Login using my Python App's FastAPI's login API.*/
  login(email: string, password: string): Observable<any> {
    const body = new URLSearchParams();
    body.set('email', email);
    body.set('password', password);

    return this.http.post<{ access_token: string }>(
      '/api/v1/login',
      body.toString(),
      {
        headers: new HttpHeaders({ 'Content-Type': 'application/x-www-form-urlencoded' }),
        withCredentials: true
      }
    ).pipe(
      tap(res => this.setSession(res.access_token))
    );
  }

  /** Allow a new user to signup */
  signup(email: string, password: string): Observable<any> {
    return this.http.post('/api/v1/signup', { email, password });
  }

  /** Refresh token when it expires. */
  refresh(): Observable<any> {
    return this.http.post<{ access_token: string }>(
      '/api/v1/refresh',
      {},
      { withCredentials: true }
    ).pipe(
      tap(res => this.setSession(res.access_token))
    );
  }

  logout(): void {
    this.accessToken$.next(null);
    this.userPayload$.next(null);
  }

  /** Decode JWT and update session state */
  private setSession(token: string) {
    this.accessToken$.next(token);
    const payload: JWTPayload = jwtDecode(token);
    this.userPayload$.next(payload);
  }

  /** Convert expires field to Date */
  getUserID(): string | null {
    const payload = this.userPayload$.value;
    return payload ? payload.id : null;
  }

  getUserPermissions(): string[] | null {
    const payload = this.userPayload$.value;
    return payload ? payload.permissions : null;
  }

  /** Convert expires field to Date */
  getTokenExpiration(): Date | null {
    const payload = this.userPayload$.value;
    return payload ? new Date(payload.expires) : null;
  }

  isAllowed(permissions: string[]): boolean {
    let currPermissions = this.getUserPermissions();
    console.log("Permissions")
    console.log(permissions)
    console.log(currPermissions)
    if (currPermissions != null){
      // User must have each required permission
      return permissions.every(permission => currPermissions.includes(permission));
    }
    else if (permissions.length > 0) {
      return false; // User has no permissions so not allowed
    }
    else{
      return true; // No permissions required
    }
  }
}
