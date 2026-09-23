using CleanCore.Application.Common.Interfaces;
using CleanCore.Domain.Common;
using CleanCore.Domain.Errors;
using MediatR;
using Microsoft.EntityFrameworkCore;

namespace CleanCore.Application.Features.Auth.Commands.Login;

public sealed class LoginCommandHandler(
    IApplicationDbContext dbContext,
    IPasswordHasher passwordHasher,
    ITokenService tokenService)
    : IRequestHandler<LoginCommand, Result<AuthResponse>>
{
    public async Task<Result<AuthResponse>> Handle(LoginCommand request, CancellationToken cancellationToken)
    {
        var email = request.Email.Trim().ToLowerInvariant();
        var user = await dbContext.Users.FirstOrDefaultAsync(
            candidate => candidate.Email == email && !candidate.IsDeleted,
            cancellationToken);

        if (user is null || !passwordHasher.Verify(request.Password, user.PasswordHash))
        {
            return Result.Failure<AuthResponse>(UserErrors.InvalidCredentials);
        }

        var accessToken = tokenService.GenerateAccessToken(user);
        var refreshToken = tokenService.GenerateRefreshToken();
        refreshToken.Id = refreshToken.Id == Guid.Empty ? Guid.NewGuid() : refreshToken.Id;
        refreshToken.UserId = user.Id;
        refreshToken.CreatedAtUtc = DateTime.UtcNow;

        dbContext.RefreshTokens.Add(refreshToken);
        await dbContext.SaveChangesAsync(cancellationToken);

        return Result.Success(new AuthResponse(accessToken, refreshToken.Token));
    }
}
