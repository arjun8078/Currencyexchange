import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ConvertResult,
  CurrencyService,
} from './currency.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  private readonly currencyApi = inject(CurrencyService);

  currencies = signal<string[]>(['INR', 'USD', 'AED', 'EUR', 'GBP']);
  provider = signal('…');
  loading = signal(false);
  error = signal<string | null>(null);
  result = signal<ConvertResult | null>(null);

  amount = 10000;
  from = 'INR';
  to = 'USD';
  date = new Date().toISOString().slice(0, 10);

  ngOnInit(): void {
    this.currencyApi.listCurrencies().subscribe({
      next: (res) => {
        this.currencies.set(res.currencies);
        this.provider.set(res.provider);
      },
      error: () => {
        this.error.set(
          'Cannot reach Django API on port 43125. Start the backend first.'
        );
      },
    });
  }

  swap(): void {
    const previousFrom = this.from;
    this.from = this.to;
    this.to = previousFrom;
    this.result.set(null);
  }

  convert(): void {
    this.error.set(null);
    this.result.set(null);

    if (!this.amount || this.amount < 0) {
      this.error.set('Enter a valid non-negative amount.');
      return;
    }
    if (!this.date) {
      this.error.set('Pick the date whose FX rate should apply.');
      return;
    }

    this.loading.set(true);
    this.currencyApi
      .convert({
        amount: this.amount,
        from: this.from,
        to: this.to,
        date: this.date,
      })
      .subscribe({
        next: (res) => {
          this.result.set(res);
          this.provider.set(res.provider);
          this.loading.set(false);
        },
        error: (err) => {
          const detail =
            err?.error?.detail ||
            err?.message ||
            'Conversion failed. Check API and date.';
          this.error.set(detail);
          this.loading.set(false);
        },
      });
  }
}
