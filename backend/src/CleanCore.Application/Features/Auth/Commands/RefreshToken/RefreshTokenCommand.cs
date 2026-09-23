using CleanCore.Domain.Common;
using MediatR;

namespace CleanCore.Application.Features.Auth.Commands.RefreshToken;

public sealed record RefreshTokenCommand(string Token) : IRequest<Result<AuthResponse>>;

public static class RefreshTokenErrors
{
    public static readonly Error Invalid = new(
        "Auth.InvalidRefreshToken",
        "The refresh token is invalid or expired.");
}
