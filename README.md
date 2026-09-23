# Enterprise Clean Architecture Boilerplate (.NET 9 + Next.js 15)

```text
  ██████╗██╗     ███████╗ █████╗ ███╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║██╔════╝██╔═══██╗██╔══██╗██╔════╝
 ██║     ██║     █████╗  ███████║██╔██╗ ██║██║     ██║   ██║██████╔╝█████╗
 ██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║██║     ██║   ██║██╔══██╗██╔══╝
 ╚██████╗███████╗███████╗██║  ██║██║ ╚████║╚██████╗╚██████╔╝██║  ██║███████╗
  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
```

> ASP.NET Core (.NET 9), Next.js 15 (App Router, React 19), PostgreSQL ve Docker Compose için tasarlanmış tam yığın başlangıç şablonu. Backend katmanları Infrastructure'a kadar repoda duruyor. WebApi bağlantısı, frontend ve Docker Compose yol haritasında.

Ayrıntılı belgeler daha sonra eklenecek. İçindekiler şimdilik bu dosyadaki başlıklara gider.

## İçindekiler

1. [Neden Bu Şablon?](#neden-bu-şablon)
2. [Temel Mimari ve Tasarım İlkeleri](#temel-mimari-ve-tasarım-ilkeleri)
3. [İstek Yaşam Döngüsü](#istek-yaşam-döngüsü)
4. [Katman Sorumlulukları ve Sınırları](#katman-sorumlulukları-ve-sınırları)
5. [Öne Çıkan Teknik Yetenekler](#öne-çıkan-teknik-yetenekler)
6. [Proje Ağacı](#proje-ağacı)
7. [Yapay Zeka Ajanları ile Kullanım](#yapay-zeka-ajanları-ile-kullanım)
8. [Hızlı Başlangıç](#hızlı-başlangıç)
9. [Yol Haritası](#yol-haritası)
10. [Lisans ve Katkıda Bulunma](#lisans-ve-katkıda-bulunma)

## Neden Bu Şablon?

Yapay zeka kodlama asistanları özellikleri hızlı yazar. Önlerinde sabit bir mimari yoksa iş mantığını controller içine yığar, veritabanı sorgusunu arayüze taşır ve token'ı `localStorage` içinde bırakır.

Bu şablon, o özelliklerin uyması gereken sınırları baştan koyar.

| Özellik | Sıradan yapay zeka prototipi | Bu şablon |
| --- | --- | --- |
| Katman izolasyonu | Arayüz ve veritabanı kodu karışık | Clean Architecture. `Domain` katmanının paket veya proje referansı yok |
| Hata yönetimi | Yakalanmayan exception, 500 ekranı | Handler'lar `Result` / `Result<T>` döner. RFC 7807 Problem Details, WebApi adımında gelecek |
| Kimlik doğrulama | `localStorage` içindeki access token | JWT access token ve dönen refresh token. HttpOnly, Secure, `SameSite=Lax` çerez hedefi; henüz bağlanmadı |
| Veri doğrulama | Handler içinde dağınık `if` | MediatR `ValidationBehavior` ile FluentValidation. Hata `Result.Failure` olur, exception fırlatılmaz |
| Veritabanı erişimi | Controller içinde `DbContext` | Handler'lar yalnızca `IApplicationDbContext` kullanır |
| Canlıya alma | El ile kurulum | `main` ve `dev` push'larında GitHub Actions çözümü derler ve test eder. Docker Compose henüz yok |

## Temel Mimari ve Tasarım İlkeleri

Backend, Clean Architecture ve CQRS izler. Bağımlılık içeri doğrudur: WebApi → Infrastructure → Application → Domain.

```text
 ┌─────────────────────────────────────────────────────────┐
 │                   Presentation / WebApi                 │
 │             (Minimal API'ler, Middleware, DI)           │
 └────────────────────────────┬────────────────────────────┘
                              │
 ┌────────────────────────────▼────────────────────────────┐
 │                     Infrastructure                      │
 │         (PostgreSQL, EF Core, BCrypt, JWT Üretimi)      │
 └────────────────────────────┬────────────────────────────┘
                              │
 ┌────────────────────────────▼────────────────────────────┐
 │                      Application                        │
 │       (CQRS Handler'ları, FluentValidation, Arayüzler)  │
 └────────────────────────────┬────────────────────────────┘
                              │
 ┌────────────────────────────▼────────────────────────────┐
 │                         Domain                          │
 │      (Entity'ler, Value Object'ler, Domain Hataları)    │
 │                    Sıfır harici bağımlılık              │
 └─────────────────────────────────────────────────────────┘
```

WebApi henüz `AddApplication()` veya `AddInfrastructure()` çağırmaz. HTTP girişi hâlâ şablondaki hava durumu ucudur.

## İstek Yaşam Döngüsü

Auth komutları bu boru hattı için yazıldı. WebApi bu komutları henüz dağıtmıyor.

```text
[İstemci / Next.js]
        │
        │ HTTP POST /api/auth/register
        ▼
[WebApi ucu] ──────────── gövdeyi RegisterCommand yapar
        │
        ▼
[MediatR]
        │
        ▼
[ValidationBehavior] ──── FluentValidation
        │                ├── geçersiz: Result.Failure
        │                └── geçerli: devam
        ▼
[RegisterCommandHandler]
        │
        ├── e-posta kullanımdaysa UserErrors.EmailAlreadyInUse
        ├── şifre IPasswordHasher ile hash'lenir
        └── User, IApplicationDbContext ile kaydedilir
        │
        ▼
[Result<Guid>]

Login ve refresh Result<AuthResponse> döner (access token + refresh token).
Refresh, kayıtlı token'ı iptal edip yenisini üretir.
```

`Register` şu an `Result<Guid>` döner. `201` ve HttpOnly çerez, WebApi bağlanınca gelecek.

## Katman Sorumlulukları ve Sınırları

### CleanCore.Domain

- NuGet paketi ve proje referansı yok.
- `BaseEntity` (`Id`, `CreatedAtUtc`, `UpdatedAtUtc`, `IsDeleted`), `User`, `RefreshToken`, `Role`.
- `Error` alanları `Code` ve `Message`. Ayrıca `Result` / `Result<T>`.
- `UserErrors`: `EmailAlreadyInUse`, `InvalidCredentials`, `NotFound`.

### CleanCore.Application

- Tek proje referansı `CleanCore.Domain`.
- Paketler: MediatR 12.5.0, FluentValidation 12.1.1 ve `DbSet<T>` için Entity Framework Core 9. Handler'lar somut `DbContext` almaz.
- Komutlar: `Register`, `Login`, `RefreshToken`. Query henüz yok.
- `ValidationBehavior` doğrulama hatalarını `Result.Failure` yapar.
- `AddApplication()` MediatR, validator ve behavior kayıtlarını ekler.

### CleanCore.Infrastructure

- Proje referansı `CleanCore.Application`. Domain bu referansın üzerinden gelir.
- `PasswordHasher` BCrypt.Net-Next kullanır.
- `TokenService` JWT access token üretir. Refresh token 64 baytlık rastgele değerdir ve 7 gün yaşar. Rotasyon `RefreshTokenCommandHandler` içindedir.
- `ApplicationDbContext` `users` ve `refresh_tokens` tablolarını kurar. E-posta ve refresh token değeri benzersizdir. `IsActive` kolon değildir.
- `AddInfrastructure` DbContext, `IPasswordHasher`, `ITokenService` ve `JwtOptions` kayıtlarını ekler.
- Ayağa kalkınca `ConnectionStrings:DefaultConnection`, `Jwt:Issuer`, `Jwt:Audience`, en az 32 karakterlik `Jwt:SecretKey` ve `Jwt:ExpirationInMinutes` gerekir.
- Migration henüz üretilmedi.

### CleanCore.WebApi

- .NET 9 Web API şablonu duruyor: Development ortamında `MapOpenApi()` ve `GET /weatherforecast`.
- Infrastructure'a bağlı değil. Auth ucu, CORS, Serilog ve global exception middleware yok.

### frontend/

Repoda yok. Hedef: Next.js 15 App Router, TypeScript, Tailwind CSS, shadcn/ui ve `middleware.ts` ile rota koruması.

## Öne Çıkan Teknik Yetenekler

- Dört katman ve içeri bakan proje referansları.
- Result pattern ve domain hataları.
- Auth komutları, FluentValidation ve `ValidationBehavior`.
- PostgreSQL eşlemesi, BCrypt ve JWT / refresh token üretimi.
- GitHub Actions: `main` veya `dev` push'unda `backend/CleanCore.sln` Release derlenir, ardından `dotnet test` çalışır. Test projesi olmadığı için bu adım şimdilik test bulamaz.

## Proje Ağacı

```text
Enterprise-Clean-Architecture-Boilerplate/
├── .cursorrules.ini
├── .github/workflows/ci.yml
├── README.md
└── backend/
    ├── CleanCore.sln
    └── src/
        ├── CleanCore.Domain/
        │   ├── Common/          BaseEntity, Error, Result
        │   ├── Entities/        User, RefreshToken, Role
        │   └── Errors/          DomainErrors (UserErrors)
        ├── CleanCore.Application/
        │   ├── Common/Behaviors/ValidationBehavior.cs
        │   ├── Common/Interfaces/
        │   ├── Features/Auth/AuthResponse.cs
        │   ├── Features/Auth/Commands/Register/
        │   ├── Features/Auth/Commands/Login/
        │   ├── Features/Auth/Commands/RefreshToken/
        │   └── DependencyInjection.cs
        ├── CleanCore.Infrastructure/
        │   ├── Authentication/  JwtOptions, PasswordHasher, TokenService
        │   ├── Persistence/ApplicationDbContext.cs
        │   └── DependencyInjection.cs
        └── CleanCore.WebApi/    şablon Program.cs ve appsettings
```

Henüz yok: `docker-compose.yml`, auth endpoint'leri, `GlobalExceptionMiddleware`, EF migration'ları ve `frontend/`.

## Yapay Zeka Ajanları ile Kullanım

Mimari kurallar [`.cursorrules.ini`](.cursorrules.ini) dosyasındadır.

### Yeni bir özellik eklerken

> `.cursorrules.ini` kurallarına uy. Domain içine `Product` ekle. Application içinde FluentValidation ile doğrulanan ve `Result<Guid>` dönen `CreateProductCommand` yaz. Infrastructure'da EF Core eşlemesini yap. WebApi ucu komutu yalnızca MediatR üzerinden göndersin.

### Mimariyi denetlerken

> Yeni dosyaları incele. Application somut `DbContext`'e bağlanmasın. Beklenen hatalar exception fırlatmak yerine `Result.Failure` dönsün.

## Hızlı Başlangıç

### Ön koşullar

- [.NET 9 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)
- Frontend gelince [Node.js 20+](https://nodejs.org/)
- Compose gelince [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Repoyu klonlayın

```bash
git clone https://github.com/zonearea/Enterprise-Clean-Architecture-Boilerplate.git
cd Enterprise-Clean-Architecture-Boilerplate
```

### Backend'i derleyin

```bash
cd backend
dotnet build CleanCore.sln
dotnet run --project src/CleanCore.WebApi
```

- HTTP: `http://localhost:5080/weatherforecast`
- HTTPS profili: `https://localhost:7295` ve `http://localhost:5080`
- Development OpenAPI belgesi: `http://localhost:5080/openapi/v1.json`

`docker compose up` henüz yok. Auth uçları bağlı olmadığı için bu çalıştırma PostgreSQL istemez.

## Yol Haritası

- [x] Solution iskeleti ve katman referansları
- [x] Domain entity'leri, Result pattern ve domain hataları
- [x] Application CQRS, FluentValidation ve validation behavior
- [x] Infrastructure: PostgreSQL EF Core eşlemesi, BCrypt ve JWT `TokenService`
- [x] GitHub Actions derleme ve test workflow'u
- [ ] WebApi auth uçları, bu rotalar için OpenAPI ve global exception middleware (RFC 7807)
- [ ] EF Core migration'ları
- [ ] Next.js 15 auth ekranları, dashboard ve token yönetimi
- [ ] PostgreSQL, API ve web için Docker Compose

## Lisans ve Katkıda Bulunma

Proje MIT Lisansı altındadır. Katkı ve pull request'ler kabul edilir.
