using System.Security.Claims;
using CleanCore.Application.Features.Auth.Commands.Login;
using CleanCore.Application.Features.Auth.Commands.RefreshToken;
using CleanCore.Application.Features.Auth.Commands.Register;
using CleanCore.Infrastructure.Authentication;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace CleanCore.WebApi.Controllers;

[Route("api/auth")]
public sealed class AuthController(ISender sender, IOptions<JwtOptions> jwtOptions) : BaseApiController
{
    public const string AccessCookieName = "accessToken";
    public const string RefreshCookieName = "refreshToken";

    [HttpPost("register")]
    [ProducesResponseType(StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> Register(RegisterRequest request, CancellationToken cancellationToken)
    {
        var result = await sender.Send(
            new RegisterCommand(request.Email, request.Password, request.FirstName, request.LastName),
            cancellationToken);

        return FromResult(result, id => Created("/api/auth/me", new { id }));
    }

    [HttpPost("login")]
    [ProducesResponseType(typeof(AccessTokenResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> Login(LoginRequest request, CancellationToken cancellationToken)
    {
        var result = await sender.Send(new LoginCommand(request.Email, request.Password), cancellationToken);

        return FromResult(result, response =>
        {
            AppendAuthCookies(response.AccessToken, response.RefreshToken);
            return Ok(new AccessTokenResponse(response.AccessToken));
        });
    }

    [HttpPost("logout")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public IActionResult Logout()
    {
        var options = AuthCookieOptions();
        Response.Cookies.Delete(AccessCookieName, options);
        Response.Cookies.Delete(RefreshCookieName, options);
        return NoContent();
    }

    [HttpPost("refresh")]
    [ProducesResponseType(typeof(AccessTokenResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> Refresh(CancellationToken cancellationToken)
    {
        if (!Request.Cookies.TryGetValue(RefreshCookieName, out var refreshToken) ||
            string.IsNullOrWhiteSpace(refreshToken))
        {
            return ToProblem(RefreshTokenErrors.Invalid);
        }

        var result = await sender.Send(new RefreshTokenCommand(refreshToken), cancellationToken);
        if (result.IsFailure || result.Value is null)
        {
            var options = AuthCookieOptions();
            Response.Cookies.Delete(AccessCookieName, options);
            Response.Cookies.Delete(RefreshCookieName, options);
            return ToProblem(result.Error);
        }

        AppendAuthCookies(result.Value.AccessToken, result.Value.RefreshToken);
        return Ok(new AccessTokenResponse(result.Value.AccessToken));
    }

    [Authorize]
    [HttpGet("me")]
    [ProducesResponseType(typeof(CurrentUserResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public IActionResult Me()
    {
        return Ok(new CurrentUserResponse(
            User.FindFirstValue(ClaimTypes.NameIdentifier),
            User.FindFirstValue(ClaimTypes.Email),
            User.FindFirstValue(ClaimTypes.GivenName),
            User.FindFirstValue(ClaimTypes.Surname),
            User.FindFirstValue(ClaimTypes.Role)));
    }

    private void AppendAuthCookies(string accessToken, string refreshToken)
    {
        Response.Cookies.Append(
            AccessCookieName,
            accessToken,
            AuthCookieOptions(DateTimeOffset.UtcNow.AddMinutes(jwtOptions.Value.ExpirationInMinutes)));

        Response.Cookies.Append(
            RefreshCookieName,
            refreshToken,
            AuthCookieOptions(DateTimeOffset.UtcNow.AddDays(7)));
    }

    private CookieOptions AuthCookieOptions(DateTimeOffset? expires = null)
    {
        return new CookieOptions
        {
            HttpOnly = true,
            Secure = Request.IsHttps,
            SameSite = SameSiteMode.Lax,
            Path = "/",
            Expires = expires,
            IsEssential = true
        };
    }
}

public sealed record RegisterRequest(string Email, string Password, string FirstName, string LastName);

public sealed record LoginRequest(string Email, string Password);

public sealed record AccessTokenResponse(string AccessToken);

public sealed record CurrentUserResponse(
    string? Id,
    string? Email,
    string? FirstName,
    string? LastName,
    string? Role);
