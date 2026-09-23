using CleanCore.Application.Common.Interfaces;
using CleanCore.Domain.Common;
using MediatR;
using Microsoft.EntityFrameworkCore;

namespace CleanCore.Application.Features.Auth.Commands.RefreshToken;

public sealed class RefreshTokenCommandHandler(
    IApplicationDbContext dbContext,
    ITokenService tokenService)
    : IRequestHandler<RefreshTokenCommand, Result<AuthResponse>>
{
    public async Task<Result<AuthResponse>> Handle(
        RefreshTokenCommand request,
        CancellationToken cancellationToken)
    {
        var storedToken = await dbContext.RefreshTokens.FirstOrDefaultAsync(
            token => token.Token == request.Token,
            cancellationToken);

        if (storedToken is null || !storedToken.IsActive)
        {
            return Result.Failure<AuthResponse>(RefreshTokenErrors.Invalid);
        }

        var user = await dbContext.Users.FirstOrDefaultAsync(
            candidate => candidate.Id == storedToken.UserId && !candidate.IsDeleted,
            cancellationToken);

        if (user is null)
        {
            return Result.Failure<AuthResponse>(RefreshTokenErrors.Invalid);
        }

        var now = DateTime.UtcNow;
        storedToken.RevokedOnUtc = now;
        storedToken.UpdatedAtUtc = now;

        var accessToken = tokenService.GenerateAccessToken(user);
        var refreshToken = tokenService.GenerateRefreshToken();
        refreshToken.Id = refreshToken.Id == Guid.Empty ? Guid.NewGuid() : refreshToken.Id;
        refreshToken.UserId = user.Id;
        refreshToken.CreatedAtUtc = now;

        dbContext.RefreshTokens.Add(refreshToken);
        await dbContext.SaveChangesAsync(cancellationToken);

        return Result.Success(new AuthResponse(accessToken, refreshToken.Token));
    }
}
