import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ConvertResult {
  amount: string;
  from: string;
  to: string;
  date_requested: string;
  rate_date: string;
  rate: string;
  converted_amount: string;
  provider: string;
  note: string;
}

export interface CurrencyList {
  currencies: string[];
  provider: string;
}

@Injectable({ providedIn: 'root' })
export class CurrencyService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://127.0.0.1:43125/api';

  listCurrencies(): Observable<CurrencyList> {
    return this.http.get<CurrencyList>(`${this.baseUrl}/currencies/`);
  }

  convert(input: {
    amount: number;
    from: string;
    to: string;
    date: string;
  }): Observable<ConvertResult> {
    const params = new HttpParams()
      .set('amount', String(input.amount))
      .set('from', input.from)
      .set('to', input.to)
      .set('date', input.date);

    return this.http.get<ConvertResult>(`${this.baseUrl}/convert/`, { params });
  }
}
